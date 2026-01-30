# Method Update Status

This file tracks per-method refactors and compatibility changes.

## Output Format Refactor (input record passthrough)
The following methods now write output records by copying the input record and appending fields (e.g. `example_idx`, `final_query`, `response`, etc.). This preserves `id` and any custom fields from the input:
- methods/artprompt.py
- methods/cipher.py
- methods/deep_inception.py
- methods/dra.py
- methods/jailbroken.py
- methods/morpheus_gapfill.py
- methods/pair.py
- methods/rene.py

## Multimodal Message Support
These methods are confirmed to use `utils.message_builder.py` (image_url-style payloads for OpenAI/Azure) when `inputs` are provided:
- methods/artprompt.py
- methods/cipher.py
- methods/deep_inception.py
- methods/dra.py
- methods/jailbroken.py
- methods/morpheus_gapfill.py
- methods/pair.py
- methods/rene.py

## Not Yet Updated (output passthrough / multimodal)
- methods/advprompter.py
- methods/autodan.py
- methods/base_attacker.py
- methods/gcg.py
- methods/gptfuzzer.py
- methods/ica.py
- methods/laa.py
- methods/mml.py
- methods/multilingual.py
- methods/overload.py
- methods/past_tense.py
- methods/random_search.py
- methods/scav.py
- methods/tap.py
