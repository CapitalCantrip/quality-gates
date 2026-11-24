# Guard the context window

The context window is finite and does not refill within a session. Spend it
only on what the next decision needs.

**Why:** A full context reasons worse, loses detail when it is compressed,
and stops progress. Every token read also costs the builder usage.

**Pattern:**
- **Read the part, not the whole.** Search first, then read the lines that
  matter; filter a command's output to the lines that answer the question.
- **Keep bulk out of the main thread.** A long log, a large document or a wide
  search comes back as a summary, not as raw text. Hand it to a subagent only
  where the project allows subagents, since one costs more usage than a
  careful read.
- **Read a file once.** Do not re-read what is already in the conversation.
- **Inline what every run uses.** A template or rule needed on every run
  belongs in the skill file, not in a separate file that costs a read each
  time.
- **Size each phase.** Cap the files a phase touches and stop to report at the
  end of each one.

**Stop:** before a read or command that could return thousands of lines,
narrow it first.

**Enforced by:** nothing yet; a judgement call.

Source: adapted from pstack's *guard-the-context-window* (Lauren Tan, MIT; LICENSE-pstack).
