---
name: ship-30-grounded-essay
description: Turn grounded Lenny's Podcast evidence into a clear, skimmable Ship 30 for 30-style essay.
source: https://www.ship30for30.com/post/how-to-start-writing-online-the-ship-30-for-30-ultimate-guide
---

# Ship 30 grounded essay skill

Use this skill only after `search_transcripts` has returned sufficient evidence. The writer's credibility is **curating the experts**: never invent personal experience, customer results, or authority.

## Required result

- Produce Markdown of approximately 1,250 words; 1,100-1,400 words is acceptable.
- Make one specific promise to one identifiable reader.
- Open with a strong hook, build a clear narrative, and finish with one useful takeaway or next action.
- Ground every podcast-derived factual claim in the supplied evidence and append an exact `[[source:ID]]` token to that sentence.
- Clearly label recommendations or experiments that are the assistant's synthesis rather than a guest's claim.
- Preserve speaker attribution, qualifications, uncertainty, and disagreement.
- If the evidence cannot support the requested thesis, narrow the thesis or explain what evidence is missing.

## Planning framework

Before drafting, establish:

1. **Specific topic:** Narrow the subject until the reader, problem, and desired outcome are concrete.
2. **Credibility:** Frame the essay as a synthesis of named podcast guests.
3. **4A angle:** Choose exactly one primary path:
   - Actionable: how the reader can act.
   - Analytical: what the evidence reveals and why.
   - Aspirational: what becomes possible, without unsupported promises.
   - Anthropological: the underlying human or organizational reason.
4. **Proven approach:** Use one consistent organizing pattern such as steps, lessons, mistakes, principles, or questions. Do not mix unrelated heading patterns.
5. **Skeleton:** Plan the headline, introduction, main sections, and conclusion before writing.

## Headline and hook

- Prefer clear over clever.
- Make the headline communicate WHAT the piece covers, WHO it helps when relevant, and WHY it is worth reading.
- Create curiosity without hiding the subject or making a promise the essay cannot keep.
- Use the opening to state the tension, the reader's stakes, the curated-expert credibility, and the promised payoff.
- A 1/3/1 rhythm works well: one short opening line, a compact explanatory middle, and one strong transition or conclusion.

## Narrative and formatting

- Move through: hook -> problem or tension -> transcript-backed insight -> implications -> concrete application -> takeaway.
- Use descriptive Markdown headings as navigational "wheels and spokes."
- Convert genuine sequences or grouped ideas into bullets; do not turn every paragraph into a list.
- Use **bold** selectively for the thesis, section takeaways, or key contrasts—not entire paragraphs.
- Alternate short emphasis lines with developed paragraphs. Avoid walls of text and avoid making every sentence its own paragraph.
- Maintain a fast rate of revelation: each sentence must add evidence, interpretation, consequence, or action.
- Keep sections balanced and transitions explicit so the essay reads as one argument rather than disconnected source summaries.

## Grounding boundary

- Use only evidence IDs returned during the current agent run.
- Never transform a guest's observation into a universal fact.
- Never attach a citation to a sentence that contains unsupported bridge claims.
- Separate `What the guests establish` from `What to try next` when proposing new experiments.
- Do not include a references dump; citations should appear beside the claims they support.
