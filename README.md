# Venture Forge

The application is in **[venture-forge](venture-forge/README.md)**. All thirteen specialists from the supplied application PDF now execute bounded tool plans and connect through five reviewed pipelines, a shared Venture Passport and a handoff ledger. Evidence capture, locked experiments and calculations remain available in their workspaces.

Start from this folder in PowerShell:

```powershell
.\Start-VentureForge.ps1
```

Open **http://127.0.0.1:3000**. Private local credentials are generated in `venture-forge/.local/local-sign-in.txt`. This local mode works without Docker and preserves records in `.local/venture-forge.sqlite3`. Keep the terminal open; Ctrl+C stops the services.

Choose **Agent Pipelines → All thirteen specialists** to run the complete connected journey. The [specialist guide](venture-forge/docs/specialist-pipelines.md) explains inputs and review gates. The [hybrid model guide](venture-forge/docs/model-routing.md) covers cloud-default complex reasoning, optional private/local processing and server-side configuration. Live search, programme feeds and external messages remain unconnected.

The original Agents Office code, notes, assets and tool server were archived before cleanup. The ZIP and a SHA-256 manifest are in **[archive](archive/)**. Every file was verified before its original was removed. The archive retains the original licence and notices; Venture Forge does not import its code or assets.

`VENTURE_FORGE_IMPLEMENTATION_PLAN.md` remains as the earlier planning reference. The application README and `docs/build-status.md` describe the current implementation and its limits.
