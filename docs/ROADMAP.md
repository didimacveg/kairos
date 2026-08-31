# Roadmap

## Built

Conversation with cloud/local failover · curated semantic memory · voice in
and out with browser wake-word detection · desktop control through a closed
whitelist · web search with sources · image understanding · daily briefing ·
Gmail and Calendar · document memory over course notes · background task
queue · reminders including open-ended ones · proactive monitoring ·
self-modification with sandbox and human approval · conversation history ·
mobile access over a private network.

Seventeen agents, 300+ tests, seventy-one documented build phases.

## Next

**Telephony.** The system can decide something is urgent but can only say it
out loud to an empty room. Phone calls are what make it useful away from the
desk.

**Hand tracking.** MediaPipe in the browser, gesture control for the HUD.

**A permanent node.** KAIROS currently dies when the PC shuts down. A
low-power mini PC would let the watcher, the agenda and the briefings run
continuously — which is the difference between a tool you launch and a system
that's simply there.

## Deliberately not built

**Fully autonomous self-modification.** The system proposes changes and a
human approves them. Removing that gate would mean a bad patch could leave
neither a working system nor a way to debug it. I've watched enough patches
fail to know the human in the loop is what makes recovery possible.

**Multi-user support.** KAIROS is built around one person's context — their
schedule, their notes, their projects. Making it general would make it worse
at the only thing it does well.
