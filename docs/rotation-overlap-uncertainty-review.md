# Overlap uncertainty correction

Independent review reproduced P1 on frozen Data103 d17e2cb, bothPython3.11/3.12 actualartifact/Math212: oldBTC raised EXECUTION_COMMIT_OUTCOME_UNKNOWN while replacementETH awaitedsubscriptionACK, then controller returnedROTATED withfailedFalse. Old.check ran only beforeawaitstart andstop/join discarded errors. The original609tests did not cover this race; frozen103 remains historical QA_FAIL for it.

Five new cases were RED before fix: oldfailure duringnewreadiness; oldclosefailure; oldfailure concurrent withnewrejection; canceledpendingconsumerACK; canceledrawcommitACK. They use actual canonicalcollector/recorder and a shared realtemporarySegmentWAL with fake sink/consumer, no provider/SQL/process.

Ownership is now accepted only after old.check followingnewreadiness, oldstop/join, old.check again and replacement.check, with noawait before assignment. Failurewhilehandlingnewstartfailure is alsorechecked; terminaluncertaintypoisonscontroller, stopsall and neverautomaticallyretries. ExactpendingWAL records areretained.

A cancelledtask is not proof that a startedcommit did not occur. PublicTradeCollector latches an in-flightexecution until literalmatchingACK is validated; a completed/cancelledcollector with an unconfirmedconsumer orrawstorageoutcome failsgroup.check. This checkprecedence prevents ordinarytask errors masking canceledcommituncertainty. Healthy in-flightcallbacks are not labeledfailed whiletheir task isstillrunning.

614scopedsourcecasesPASS withactualMath212. Native/provider/PostgreSQL/physicalWAL andfullhostedCI remainNOT_RUN orseparatelypending; Data102legacyCIsetupfailure isnotclaimedfixedhere. Source/protocol/SQL ownershipunchanged, no newwriter/resultledger/financialalgorithm. Artifact andindependentrecheck receiptafollows.
