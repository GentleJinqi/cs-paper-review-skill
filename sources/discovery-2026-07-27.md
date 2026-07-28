# Paper-Review Skill Discovery

Observed 2026-07-28. The search used the full query families below across
GitHub repository and code search. It is systematic but not
internet-exhaustive:

- `"paper review" SKILL.md`
- `"academic paper review" agent skill`
- `"peer review" Codex skill`
- `"manuscript review" SKILL.md`
- `"paper reviewer" GPT-5.6`
- `"review revision" Codex`

The GitHub CLI was unavailable, so browser/GitHub search was used without
reducing the query set. Mirrors, registries, checklist-only results, writing
style prompts, and code-review projects were not promoted.

## Screen

| Repository | Pinned commit | Relevant path | Licence | Outcome |
|---|---|---|---|---|
| [K-Dense scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | `e7ac42510774624f327003c95b6650e2883bc01d` | `skills/peer-review/SKILL.md` | MIT | full mechanism audit |
| [Conradgui Academic-Paper-Review-Skill](https://github.com/Conradgui/Academic-Paper-Review-Skill) | `9f3288f7a13e25400a8ff0c00eeb16270e37fe98` | `paper-review/SKILL.md` | MIT | full mechanism audit |
| [chunhualiao paper-review-skill](https://github.com/chunhualiao/paper-review-skill) | `c0f69fb52535412314ff99cd7d3b7f9b7bf7b8bd` | `SKILL.md` | MIT, external OCR separately unresolved | evaluation only |
| [AgentScope OpenJudge](https://github.com/agentscope-ai/OpenJudge) | `2151def3553e5521ff8b3e2fea837561c57255f9` | `skills/paper-review/SKILL.md` | Apache-2.0 | mechanism audit |
| [Meet-Reviewer-2](https://github.com/xf686/Meet-Reviewer-2) | `551d613ac5ce070d08831d0ac76cb4aac47285d4` | `skills/paper-redteam/SKILL.md` | MIT, derived-source limits | mechanism audit |
| [roast-paper-codex](https://github.com/aalvsz/roast-paper-codex) | `ca7e2d055ff1b20f54fd74306c345698bb5ce4c3` | `skills/roast-paper/SKILL.md` | MIT | full mechanism audit |
| [AgentSociety](https://github.com/tsinghua-fib-lab/AgentSociety) | `1832bcbfd657588d788263256def2e46863bf9d0` | `extension/skills/agentsociety-paper-review/v1.0.0/SKILL.md` | Apache-2.0 | full mechanism audit |
| [open-science-skills](https://github.com/scdenney/open-science-skills) | `4ecff193325bc9f4195d00ed8410ff63ba391ac3` | two non-identical paper-review paths | CC BY-NC 4.0 | reference only |
| [DeerFlow](https://github.com/bytedance/deer-flow) | `6456c35675dfbfdfc25ec5346e52ed8a8de1c5ef` | `skills/public/academic-paper-review/SKILL.md` | MIT | reject: no operational mechanism |
| [paper-lifecycle](https://github.com/M1n-n9/paper-lifecycle) | `da8a231892963b37fbb6d09e49ad5c3f7db22958` | `review-revision/SKILL.md` | unresolved | exclude |
| [Ai-Review](https://github.com/NeuroDong/Ai-Review) | `a1f27cddcff4d24c2f1422f0383fd5982233e098` | `ai-review-skills/SKILL.md` | MIT | reject: duplicate/style-only |

Recency, repository size, persona count, model-name claims, and output style
were not treated as review-quality evidence. No external source is a runtime
dependency, no upstream script was executed, and no external bytes are copied
into this core.
