# Your own ApexMind model

`apexmind` is a real model you build locally. It starts as a strong open base with
ApexMind's identity + behavior baked in, and is designed to be **upgraded in place**
over time toward a fully custom, fine-tuned model.

## Build it (free, runs on your machine)
```bash
ollama pull llama3.1                 # the default base (once)
# Windows:
model\build_apexmind.cmd
# Mac/Linux:
bash model/build_apexmind.sh
```
Then it appears in the Chat model dropdown as `apexmind`, and the router uses it by
default for reasoning/chat (with `llama3.1` as a safety fallback).

## The upgrade ladder (low → high effort)
1. **Persona & params** *(done)* — `ApexMind.Modelfile` SYSTEM + sampling. Rebuild to change.
2. **Stronger base** — change the `FROM` line to `qwen2.5:7b`, `qwen2.5-coder:7b`,
   `deepseek-r1:8b`, etc. (pull it first), then rebuild. Same name, better brain.
3. **Fine-tune (LoRA/QLoRA)** — teach it on *your* examples (your style, your domain)
   on a free Colab/Kaggle GPU. Export to GGUF and point `FROM ./apexmind-finetuned.gguf`.
   This is where it becomes genuinely *yours*, not just a re-skinned base.
4. **Continued pretraining / from-scratch** — the long game. Needs real GPUs, large
   curated datasets, and a training pipeline. Track progress here as it grows.

> Honest note: matching frontier models (Fable 5 / GLM-class) is a multi-year,
> compute-heavy effort. This ladder lets ApexMind improve continuously and stay
> 100% yours at every step — no guarantees on benchmarks, just a real path forward.

## What to prepare for fine-tuning (step 3)
- A dataset of instruction → response pairs in your voice/domain (even 200–2000 good
  examples helps). JSONL: `{"messages":[{"role":"user",...},{"role":"assistant",...}]}`.
- Ask and I'll generate a ready-to-run LoRA notebook + a script to export the result
  to GGUF and wire it into the Modelfile.
