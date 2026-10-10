from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import sqlite3,hashlib,json
from pathlib import Path

class InstrumentStatus(str,Enum):
    PRE_LISTING='PRE_LISTING'; ACTIVE='ACTIVE'; SUSPENDED='SUSPENDED'; MISSING='MISSING'; DELISTED='DELISTED'

@dataclass(frozen=True)
class InstrumentRecord:
    symbol:str; status:InstrumentStatus; first_seen:int; last_seen:int; delisted_at:int|None=None

class InstrumentRegistry:
    def __init__(self,conn,missing_confirmations:int=2): self.conn=conn;self.missing_confirmations=max(1,int(missing_confirmations))
    @classmethod
    def open(cls,path:Path):
        c=sqlite3.connect(path)
        c.execute("CREATE TABLE IF NOT EXISTS instruments(symbol TEXT PRIMARY KEY,status TEXT NOT NULL,first_seen INTEGER NOT NULL,last_seen INTEGER NOT NULL,delisted_at INTEGER,missing_count INTEGER NOT NULL DEFAULT 0)")
        cols={r[1] for r in c.execute("PRAGMA table_info(instruments)")}
        if "missing_count" not in cols:c.execute("ALTER TABLE instruments ADD COLUMN missing_count INTEGER NOT NULL DEFAULT 0")
        c.execute("CREATE TABLE IF NOT EXISTS instrument_intervals(symbol TEXT NOT NULL,start_time INTEGER NOT NULL,end_time INTEGER,PRIMARY KEY(symbol,start_time))")
        c.execute("CREATE TABLE IF NOT EXISTS instrument_registry_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        c.commit(); return cls(c)
    def close(self): self.conn.close()
    def get(self,symbol):
        row=self.conn.execute("SELECT symbol,status,first_seen,last_seen,delisted_at FROM instruments WHERE symbol=?",(symbol,)).fetchone()
        return None if row is None else InstrumentRecord(row[0],InstrumentStatus(row[1]),row[2],row[3],row[4])
    def active_symbols(self):
        return {r[0] for r in self.conn.execute("SELECT symbol FROM instruments WHERE status=?",(InstrumentStatus.ACTIVE.value,))}
    def intervals(self,symbol):
        return self.conn.execute("SELECT start_time,end_time FROM instrument_intervals WHERE symbol=? ORDER BY start_time",(symbol,)).fetchall()
    def eligible_at(self,symbol,timestamp):
        return self.conn.execute("SELECT 1 FROM instrument_intervals WHERE symbol=? AND start_time<=? AND (end_time IS NULL OR ?<end_time) LIMIT 1",(symbol,timestamp,timestamp)).fetchone() is not None
    def _set_status(self,symbol,status,observed_at,commit=True):
        rec=self.get(symbol)
        if rec is None: raise KeyError(symbol)
        if rec.status is InstrumentStatus.ACTIVE and status is not InstrumentStatus.ACTIVE:
            self.conn.execute("UPDATE instrument_intervals SET end_time=? WHERE symbol=? AND end_time IS NULL",(observed_at,symbol))
        if rec.status is not InstrumentStatus.ACTIVE and status is InstrumentStatus.ACTIVE:
            self.conn.execute("INSERT OR IGNORE INTO instrument_intervals(symbol,start_time,end_time) VALUES(?,?,NULL)",(symbol,observed_at))
        delisted=observed_at if status is InstrumentStatus.DELISTED else (None if status is InstrumentStatus.ACTIVE else rec.delisted_at)
        missing_count=0 if status is InstrumentStatus.ACTIVE else self.conn.execute("SELECT missing_count FROM instruments WHERE symbol=?",(symbol,)).fetchone()[0]
        self.conn.execute("UPDATE instruments SET status=?,last_seen=?,delisted_at=?,missing_count=? WHERE symbol=?",(status.value,observed_at,delisted,int(missing_count or 0),symbol))
        if commit:self.conn.commit()
    def set_status(self,symbol,status,observed_at):
        return self._set_status(symbol,status,observed_at,commit=True)
    def reconcile(self,exchange_snapshot:set[str],observed_at:int):
        return self.reconcile_lifecycle(
            exchange_snapshot,
            explicit_statuses={},
            terminal_times={},
            observed_at=observed_at,
        )

    def _set_explicit_delisted(
        self,
        symbol,
        observed_at,
        terminal_at,
        commit=True,
    ):
        rec=self.get(symbol)

        if rec is None:
            raise KeyError(symbol)

        observed_at=int(observed_at)
        terminal_at=int(terminal_at)

        if terminal_at<=0:
            raise ValueError(
                "terminal timestamp must be positive"
            )

        if terminal_at>observed_at:
            raise ValueError(
                "terminal timestamp cannot be in the future"
            )

        latest=self.conn.execute(
            """
            SELECT start_time,end_time
            FROM instrument_intervals
            WHERE symbol=?
            ORDER BY start_time DESC
            LIMIT 1
            """,
            (symbol,),
        ).fetchone()

        if latest is not None:
            start_time,end_time=latest

            if terminal_at<start_time:
                raise ValueError(
                    "terminal timestamp precedes active interval"
                )

            # ACTIVE:
            # close the currently open interval at Bybit deliveryTime.
            #
            # MISSING / DELISTED:
            # our earlier absence inference may have closed the final
            # interval at polling time. Explicit exchange terminal evidence
            # is authoritative and can correct that final boundary.
            #
            # SUSPENDED:
            # do NOT extend an interval that was deliberately closed by a
            # known suspension.
            if rec.status in (
                InstrumentStatus.ACTIVE,
                InstrumentStatus.MISSING,
                InstrumentStatus.DELISTED,
            ):
                self.conn.execute(
                    """
                    UPDATE instrument_intervals
                    SET end_time=?
                    WHERE symbol=? AND start_time=?
                    """,
                    (
                        terminal_at,
                        symbol,
                        start_time,
                    ),
                )

        self.conn.execute(
            """
            UPDATE instruments
            SET status=?,
                last_seen=?,
                delisted_at=?,
                missing_count=0
            WHERE symbol=?
            """,
            (
                InstrumentStatus.DELISTED.value,
                observed_at,
                terminal_at,
                symbol,
            ),
        )

        if commit:
            self.conn.commit()

    def reconcile_lifecycle(
        self,
        exchange_snapshot:set[str],
        explicit_statuses,
        terminal_times,
        observed_at:int,
    ):
        """
        Atomically reconcile the currently Trading universe together with
        explicit non-trading exchange observations.

        explicit_statuses:
            symbol -> InstrumentStatus.PRE_LISTING / SUSPENDED / DELISTED

        terminal_times:
            symbol -> authoritative exchange terminal timestamp in ms.
            Only meaningful for DELISTED.

        Unknown explicitly DELISTED instruments are ignored deliberately:
        a Closed query can contain a large historical catalogue and should
        not flood a fresh registry with instruments this installation never
        observed.
        """
        observed_at=int(observed_at)

        raw=list(exchange_snapshot)

        if any(
            not isinstance(x,str) or not x.strip()
            for x in raw
        ):
            raise ValueError(
                "instrument symbols must be non-empty strings"
            )

        symbols={x.strip() for x in raw}

        if not isinstance(explicit_statuses,dict):
            raise ValueError(
                "explicit_statuses must be a dict"
            )

        if not isinstance(terminal_times,dict):
            raise ValueError(
                "terminal_times must be a dict"
            )

        explicit={}

        for raw_symbol,raw_status in explicit_statuses.items():
            if (
                not isinstance(raw_symbol,str)
                or not raw_symbol.strip()
            ):
                raise ValueError(
                    "explicit instrument symbols must be non-empty strings"
                )

            symbol=raw_symbol.strip()

            try:
                status=(
                    raw_status
                    if isinstance(raw_status,InstrumentStatus)
                    else InstrumentStatus(raw_status)
                )
            except (TypeError,ValueError):
                raise ValueError(
                    f"invalid explicit instrument status for {symbol}"
                )

            if status is InstrumentStatus.ACTIVE:
                raise ValueError(
                    "ACTIVE belongs in exchange_snapshot, not explicit_statuses"
                )

            if status is InstrumentStatus.MISSING:
                raise ValueError(
                    "MISSING is inferred locally, not supplied explicitly"
                )

            explicit[symbol]=status

        overlap=symbols.intersection(explicit)

        if overlap:
            raise ValueError(
                "instrument cannot be both ACTIVE and explicitly non-active"
            )

        normalized_terminal={}

        for raw_symbol,raw_value in terminal_times.items():
            if (
                not isinstance(raw_symbol,str)
                or not raw_symbol.strip()
            ):
                raise ValueError(
                    "terminal symbol must be a non-empty string"
                )

            symbol=raw_symbol.strip()

            if (
                symbol not in explicit
                or explicit[symbol] is not InstrumentStatus.DELISTED
            ):
                raise ValueError(
                    "terminal timestamp requires explicit DELISTED status"
                )

            try:
                value=int(raw_value)
            except (TypeError,ValueError):
                raise ValueError(
                    f"invalid terminal timestamp for {symbol}"
                )

            if value<=0:
                raise ValueError(
                    f"invalid terminal timestamp for {symbol}"
                )

            if value>observed_at:
                raise ValueError(
                    f"future terminal timestamp for {symbol}"
                )

            normalized_terminal[symbol]=value

        # Preserve the historical digest format when this is an old-style
        # ACTIVE-only reconcile. This avoids needless incompatibility with
        # registry DBs created before explicit lifecycle support.
        if not explicit and not normalized_terminal:
            digest_payload=sorted(symbols)
        else:
            digest_payload={
                "active":sorted(symbols),
                "explicit":[
                    [symbol,explicit[symbol].value]
                    for symbol in sorted(explicit)
                ],
                "terminal":[
                    [symbol,normalized_terminal[symbol]]
                    for symbol in sorted(normalized_terminal)
                ],
            }

        digest=hashlib.sha256(
            json.dumps(
                digest_payload,
                separators=(',',':'),
                sort_keys=True,
            ).encode()
        ).hexdigest()

        meta=dict(
            self.conn.execute(
                "SELECT key,value FROM instrument_registry_meta"
            )
        )

        previous_at=(
            int(meta["last_reconcile_at"])
            if "last_reconcile_at" in meta
            else None
        )

        previous_hash=meta.get("last_snapshot_hash")

        if previous_at is not None:
            if observed_at<previous_at:
                raise ValueError(
                    "non-monotonic universe observation"
                )

            if observed_at==previous_at:
                if digest==previous_hash:
                    return

                raise ValueError(
                    "conflicting universe snapshot at identical timestamp"
                )

        self.conn.execute("BEGIN IMMEDIATE")

        try:
            known={
                r[0]:InstrumentStatus(r[1])
                for r in self.conn.execute(
                    "SELECT symbol,status FROM instruments"
                )
            }

            # Trading instruments.
            for symbol in sorted(symbols):
                if symbol not in known:
                    self.conn.execute(
                        """
                        INSERT INTO instruments(
                            symbol,
                            status,
                            first_seen,
                            last_seen,
                            delisted_at,
                            missing_count
                        )
                        VALUES(?,?,?,?,NULL,0)
                        """,
                        (
                            symbol,
                            InstrumentStatus.ACTIVE.value,
                            observed_at,
                            observed_at,
                        ),
                    )

                    self.conn.execute(
                        """
                        INSERT INTO instrument_intervals
                        VALUES(?,?,NULL)
                        """,
                        (
                            symbol,
                            observed_at,
                        ),
                    )

                elif known[symbol] is not InstrumentStatus.ACTIVE:
                    self._set_status(
                        symbol,
                        InstrumentStatus.ACTIVE,
                        observed_at,
                        commit=False,
                    )

                else:
                    self.conn.execute(
                        """
                        UPDATE instruments
                        SET last_seen=?,missing_count=0
                        WHERE symbol=?
                        """,
                        (
                            observed_at,
                            symbol,
                        ),
                    )

            # Explicit exchange observations.
            for symbol in sorted(explicit):
                status=explicit[symbol]

                if symbol not in known:
                    # Do not import the exchange's entire historical Closed
                    # catalogue into a fresh local registry.
                    if status is InstrumentStatus.DELISTED:
                        continue

                    self.conn.execute(
                        """
                        INSERT INTO instruments(
                            symbol,
                            status,
                            first_seen,
                            last_seen,
                            delisted_at,
                            missing_count
                        )
                        VALUES(?,?,?,?,NULL,0)
                        """,
                        (
                            symbol,
                            status.value,
                            observed_at,
                            observed_at,
                        ),
                    )

                    continue

                if status is InstrumentStatus.DELISTED:
                    terminal_at=normalized_terminal.get(
                        symbol,
                        observed_at,
                    )

                    self._set_explicit_delisted(
                        symbol,
                        observed_at,
                        terminal_at,
                        commit=False,
                    )

                else:
                    self._set_status(
                        symbol,
                        status,
                        observed_at,
                        commit=False,
                    )

                    # The instrument was explicitly observed by the
                    # exchange, so a previous local MISSING counter no
                    # longer applies.
                    self.conn.execute(
                        """
                        UPDATE instruments
                        SET missing_count=0
                        WHERE symbol=?
                        """,
                        (symbol,),
                    )

            observed_symbols=symbols.union(explicit)

            # Only genuinely unexplained absence consumes the local
            # MISSING -> DELISTED fallback confirmation counter.
            for symbol,status in known.items():
                if symbol in observed_symbols:
                    continue

                if status in (
                    InstrumentStatus.ACTIVE,
                    InstrumentStatus.MISSING,
                ):
                    count=int(
                        self.conn.execute(
                            """
                            SELECT missing_count
                            FROM instruments
                            WHERE symbol=?
                            """,
                            (symbol,),
                        ).fetchone()[0] or 0
                    )+1

                    if count>=self.missing_confirmations:
                        self.conn.execute(
                            """
                            UPDATE instruments
                            SET missing_count=?
                            WHERE symbol=?
                            """,
                            (
                                count,
                                symbol,
                            ),
                        )

                        self._set_status(
                            symbol,
                            InstrumentStatus.DELISTED,
                            observed_at,
                            commit=False,
                        )

                    else:
                        if status is InstrumentStatus.ACTIVE:
                            self.conn.execute(
                                """
                                UPDATE instrument_intervals
                                SET end_time=?
                                WHERE symbol=?
                                  AND end_time IS NULL
                                """,
                                (
                                    observed_at,
                                    symbol,
                                ),
                            )

                        self.conn.execute(
                            """
                            UPDATE instruments
                            SET status=?,missing_count=?
                            WHERE symbol=?
                            """,
                            (
                                InstrumentStatus.MISSING.value,
                                count,
                                symbol,
                            ),
                        )

            self.conn.execute(
                """
                INSERT OR REPLACE INTO instrument_registry_meta(
                    key,
                    value
                )
                VALUES('last_reconcile_at',?)
                """,
                (str(observed_at),),
            )

            self.conn.execute(
                """
                INSERT OR REPLACE INTO instrument_registry_meta(
                    key,
                    value
                )
                VALUES('last_snapshot_hash',?)
                """,
                (digest,),
            )

            self.conn.commit()

        except Exception:
            self.conn.rollback()
            raise
