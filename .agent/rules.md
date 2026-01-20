# Agent Rules for ICT Trainer Project

## Git Management Rules

### ⚠️ **CRITICAL: DO NOT AUTO-PUSH**

**Rule:** Only push to GitHub when:
1. **User explicitly requests it** ("push", "commit and push", etc.)
2. **Every 100 messages** in a conversation (to prevent data loss)

**Default workflow:**
- ✅ Make changes to files
- ✅ Commit locally with descriptive messages
- ❌ **DO NOT** automatically push

**Why:** 
- Reduces unnecessary remote operations
- Gives user control over what gets pushed
- Prevents GitHub rate limiting
- User can review local commits before pushing

---

## Data Management Rules

### Large File Handling
- **Never commit** raw chat export JSON files (>100MB)
- Files to exclude:
  - `docs/*.json` (chat exports)
  - `docs/*_readable.md` (unless small)
  - `docs/convert_chat_to_markdown.py`

### Screenshot Organization
- All training screenshots → `screenshots/training/positive/` or `/negative/`
- Naming: `YYYY-MM-DD_SESSION_PAIR_SETUP_NUM[_timeframe].png`
- Always link in trade JSON `references.screenshots` array

---

## Workflow Preferences

### Communication
- Provide progress updates without pushing
- Commit locally with good messages
- Let user know commits are ready but not pushed

### Validation
- Always validate JSON schemas before committing
- Run `python scripts/validate_setup.py --all` before finalizing

---

**Last Updated:** 2026-01-20
