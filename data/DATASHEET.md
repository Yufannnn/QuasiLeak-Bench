# Datasheet

**Purpose.** Evaluate detectors that recover quasi-evidence groups, cues weak alone and
revealing together, under a per-recipient disclosure policy.

**Composition.** 5,000 first-person messages from 500 synthetic sender profiles across 20
communication contexts, with 9,099 verified groups of two to four cues, 23,041 cues, and
12,237 planted distractors. A 1,000-document subset follows the full corpus's
distributions.

**Collection.** Reverse construction (Section 4 of the paper): cue mining, group
construction, and document writing, with GPT-5.5 as proposer and writer and
Claude-Opus-4.8 as verifier, followed by a rubric-based quality check and expert review.
300 profiles are adapted from SynthPAI; 200 were generated for this benchmark.

**Personal information.** None. All profiles and documents are synthetic.

**Intended use.** Evaluating and training sender-side privacy detectors.

**License.** CC BY-NC-SA 4.0. File hashes are in `metadata/`.
