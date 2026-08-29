Quick dev checklist — run these in separate terminals

1) Start dev server (background tasks disabled, default):

PowerShell
```
./run-development.ps1
```

2) To start server with background tasks (monitoring, search scheduler) enabled:

PowerShell
```
./run-development-with-bg.ps1
```

Note: enabling background tasks may call external APIs (YouTube, Firebase). Make sure the following env vars in `.env.development` are set if you enable background tasks:
- `API_KEY` (YouTube API key)
- `PLAYLIST_ID`
- `SERVICE_ACCOUNT_FILE` and `PROJECT_ID` for FCM

3) Smoke check endpoints (after server is running):

Python
```
python dev_smoke_checks.py
```

4) Simulate milestone crossing without sending real FCM notifications:

Python
```
python dev_test_milestone.py
```

If you want, I can change `.env.development` to enable `START_BACKGROUND_TASKS=true` automatically — confirm before I patch it.
