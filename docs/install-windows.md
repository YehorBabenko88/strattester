# Windows installation

Default installation root is **C:\ProgramData\Strattester**.

Run an elevated PowerShell from a checked-out release:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Runtime layout:

- `C:\ProgramData\Strattester\data` — market databases
- `state` — durable scheduler/controller state
- `results` — backtest outputs
- `logs` — application/service logs
- `releases` — immutable code releases
- `config` — local configuration/secrets

Do not put Telegram tokens or remote-access keys in GitHub.
