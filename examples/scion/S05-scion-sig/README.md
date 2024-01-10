# SCION IP Gateway in SEED

## Work in Progress
Limitations at the moment:
- Only one SIG per AS
- Requires a CS called `cs1` in the AS before calling "createSig" or "connect"
- SIG Runs on the CS node
- Tested so far only from the CS node (the SIG ip is on dev lo, which needs to be changed probably)