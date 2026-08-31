# Roadmap

## Done

Conversation with cloud/local failover · curated semantic memory · voice in
and out with wake word · desktop control through a closed whitelist · web
search with sources · image understanding · daily briefing · Gmail and
Calendar · document memory over course notes · background task queue ·
reminders including open-ended ones · proactive monitoring · self-modification
with sandbox and human approval · conversation history · mobile access over a
private network.

## Next

**Phone calls.** The system can decide something is urgent but can only say it
out loud to an empty room. Telephony is what makes it useful when I'm not at
the desk.

**Hand tracking.** MediaPipe in the browser. Gesture control for the HUD.

**A permanent node.** Right now KAIROS dies when I shut down the PC. A
low-power mini PC would let the watcher, the agenda and the briefings run
continuously.

## Deliberately not built

**Fully autonomous self-modification.** The system proposes changes and I
approve them. Removing that gate would mean a bad patch could leave me with
neither a working system nor a way to debug it — I've watched patches fail
often enough to know the human in the loop is what makes recovery possible.

**Automated trading or anything with real money.** The architecture would
support it. The decision not to is about what the system is for.

**Multi-user support.** KAIROS is built around one person's context. Making
it general would make it worse at the only thing it does well.
