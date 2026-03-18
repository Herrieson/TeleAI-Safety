# Method Update Status

This file tracks per-method refactors and compatibility changes.

## Model Deployment Compatibility (`methods/`)
Classification basis used below:
- `Local-only`: the main attack path depends on local-only capabilities such as direct `model/tokenizer` access, trainable parameters, or gradient-based optimization.
- `API + Local`: target model can be loaded via unified `load_model` and used through chat-style interfaces for both API models and local models.

### Local-Only (open-source local deployment required)
- methods/advprompter.py
- methods/autodan.py
- methods/gcg.py

### API + Local (both supported)
- methods/artprompt.py
- methods/cipher.py
- methods/deep_inception.py
- methods/dra.py
- methods/gptfuzzer.py
- methods/ica.py
- methods/jailbroken.py
- methods/laa.py
- methods/minimal_example.py
- methods/morpheus_gapfill.py
- methods/multilingual.py
- methods/overload.py
- methods/pair.py
- methods/past_tense.py
- methods/random_search.py
- methods/rene.py
- methods/scav.py
- methods/tap.py

### Notes
- `methods/artprompt.py`: `target_model` supports API/local, but `mask_model` is currently fixed to Azure API, so fully offline execution is not supported.
- `methods/laa.py`: supports API/local, but to best preserve original optimization intent it is preferable to run with a model/backend that supports token-level `logprobs` via `get_response`; otherwise it falls back to heuristic pseudo-logprob scoring.
- `methods/base_attacker.py`: framework base class, not an attack method; excluded from compatibility classification.

## Model Deployment Compatibility (`methods/txt_img/`)
### API + Local (both supported)
- methods/txt_img/bap.py
- methods/txt_img/HIMRD-merge.py
- methods/txt_img/JOOD-merge.py
- methods/txt_img/mml.py
- methods/txt_img/SI_Attack-merge.py
- methods/txt_img/viscra.py

### Notes
- `methods/txt_img/viscra.py`: target model supports API/local, but the attention-map generation stage requires an extra local vision model (`attention_model_path`).

## Intent Preservation Constraints
To preserve the original method intent as much as possible:
- `Local-only` methods (`advprompter`, `autodan`, `gcg`) should be treated as strictly local-model attacks.
- `API + Local` methods are classified as such because their core attack loop uses unified `load_model` + chat interfaces; however, methods with additional constraints in Notes should follow those constraints.

## Access Assumption (White-box)
The following methods are implemented with white-box assumptions in this repo (local model internals required):
- `methods/gcg.py`: white-box gradient/logits optimization over token-level objectives.
- `methods/advprompter.py`: white-box parameter optimization (`optimizer` + `loss.backward()`) for the prompter model.
- `methods/autodan.py`: white-box logits/loss evaluation (computes token-level CE loss from target-model forward logits; does not rely on gradient backprop in the current attack loop).

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
- methods/gptfuzzer.py
- methods/ica.py
- methods/multilingual.py
- methods/overload.py
- methods/past_tense.py
- methods/laa.py
- methods/random_search.py
- methods/scav.py
- methods/tap.py

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
- methods/gptfuzzer.py
- methods/ica.py
- methods/multilingual.py
- methods/overload.py
- methods/past_tense.py
- methods/laa.py
- methods/random_search.py
- methods/scav.py
- methods/tap.py

## Not Yet Updated (output passthrough / multimodal)
- methods/advprompter.py
- methods/autodan.py
- methods/base_attacker.py
- methods/gcg.py
