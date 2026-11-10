# Smali Obfuscation in the Era of LLMs: Should I Stay or Should I Go?

This repository contains the replication material for the empirical study **"Smali Obfuscation in the Era of LLMs: Should I Stay or Should I Go?"**. The study compares two Android Smali transformation paradigms:

1. **Deterministic transformations**, applied independently to each APK.
2. **LLM-assisted transformations**, where deterministic structural analysis and suitability scoring assign candidate files and transformation types, while a local LLM generates the corresponding Smali modifications.

The experiments use 500 Android malware APKs from ten malware families and six functional categories. Malware binaries are **not redistributed** in this repository. Reproducibility is supported through SHA-256 identifiers, metadata, transformation scripts, prompt/configuration material, and raw experimental results.

## Research Questions

- **RQ1:** How effective are individual deterministic Smali transformation techniques in challenging static detection for different Android malware families?
- **RQ2:** How effectively and reliably do the LLM-assisted transformation pipelines challenge static detection for various Android malware families?
- **RQ3:** Do LLM-assisted transformation pipelines provide measurable advantages over deterministic techniques in static detection evasion effectiveness and sample-specific adaptation?
## Transformation Techniques

Both experimental branches operate over the same five transformation categories:

- **String Obfuscation (SO)**
- **Dead Code Injection (DCI)**
- **Reflection-Based Call (RBC)**
- **Benign Dummy Class Injection (BDC)**
- **Opaque Predicates (OP)**

In the LLM-assisted branch, the LLM does **not** independently select the file or transformation technique. Candidate files and transformation types are assigned by deterministic structural analysis and suitability scoring. Qwen2.5-Coder:14B and Mistral-Nemo:12B are then used as generative components to produce the requested Smali modifications.

## Dataset

The initial corpus contains **500 unique Android malware APKs** belonging to ten malware families:

| Category | Families | Samples |
|---|---|---:|
| Banking Trojan | Alien, Cerberus, GoldDigger, Hydra | 200 |
| Trojan | Fakecop, Irata | 100 |
| RAT | SpyNote | 50 |
| SMS Stealer | SMSAgent | 50 |
| Spyware | Joker | 50 |
| Stalkerware | TiSpy | 50 |
| **Total** | **10 families** | **500** |

The primary source is **MalwareBazaar**, with 489 samples. The remaining 11 samples were obtained from **AndroZoo**, primarily to complete the GoldDigger subset.

The repository contains sample identifiers and metadata only. Researchers who are authorized to access the original malware must obtain the APKs independently from the corresponding providers.

## Repository Structure

```text
.
├── README.md
├── .gitignore
├── data/
│   └── android_malware_metadata.xlsx
│
├── deterministic/
│   ├── scripts/
│   │   ├── 01_decompile_apk.py
│   │   ├── 02_dead_code_injection.py
│   │   ├── 02_opaque_predicates.py
│   │   ├── 03_rebuild_apk_windows_v3.py
│   │   ├── 03b_string_obfuscation.py
│   │   ├── benign_dummy_class.py
│   │   ├── reflection_based_call.py
│   │   ├── download_androzoo.py
│   │   ├── download_malwarebazaar.py
│   │   ├── virustotal_upload_analysis.py
│   │   └── generate_comparison_plots.py
│   └── results/
│       ├── string_obfuscation/
│       ├── dead_code_injection/
│       ├── reflection_based_call/
│       ├── benign_dummy_class/
│       └── opaque_predicates/
│
├── llm_assisted/
│   ├── prompts/
│   │   ├── README.md
│   ├── config/
│   │   └── README.md
│   └── results/
│       ├── qwen2.5_results.jsonl
│       ├── mistral-nemo_results.jsonl
│       ├── qwen2.5_failed_samples.csv
│       └── mistral-nemo_failed_samples.csv

```


## Deterministic Branch

The deterministic branch applies each transformation independently. The general workflow is:

```text
APK acquisition
    -> decompilation with APKTool
    -> deterministic Smali transformation
    -> APK rebuild
    -> signing
    -> VirusTotal evaluation
    -> original/transformed comparison
```

The experiments used **APKTool 3.0.2** for the deterministic branch. Each transformation is implemented by a dedicated Python script, allowing the effect of individual transformations to be analyzed separately.

## LLM-Assisted Branch

The LLM-assisted pipeline evaluates:

- **Qwen2.5-Coder:14B**
- **Mistral-Nemo:12B**

Both models were executed locally through **Ollama**, using an 8,192-token context window and a temperature of 0.1.

For each sample, the pipeline:

1. analyzes non-library Smali files;
2. computes technique-specific suitability scores;
3. assigns candidate files and transformation types;
4. requests the selected transformation from the LLM;
5. validates the generated Smali code;
6. applies fallback transformations when required;
7. selectively restores problematic files when rebuild failures occur;
8. rebuilds and signs the transformed APK;
9. evaluates the original and transformed samples using VirusTotal.

The exact prompt templates, technique-specific examples, and experiment configuration should be included under `llm_assisted/prompts/` and `llm_assisted/config/`.

## Evaluation Metrics

For each APK, the normalized VirusTotal detection score is:

```text
Score = (Malicious + Suspicious) /
        (Malicious + Suspicious + Undetected)
```

The evasion delta is:

```text
Delta = Score_original - Score_modified
```

A positive delta indicates a reduction in the normalized detection score after transformation.

For the LLM-assisted pipelines, the repository also reports operational information such as the number of applied techniques, successfully modified files, file-level success rate, and fallback events.

## Main Results

The principal aggregate results reported in the paper are:

- **Opaque Predicates:** mean evasion delta = 0.2407; mean relative score reduction = 49.5%.
- **Qwen-based pipeline:** mean evasion delta = 0.2320; mean relative score reduction = 48.8%.
- **Mistral-based pipeline:** mean evasion delta = 0.2359; mean relative score reduction = 48.8%.
- On the 182 APKs with complete cross-branch results, the pipeline-assigned transformation set includes the sample-specific best deterministic technique in **28.6%** of Qwen-based cases and **37.9%** of Mistral-based cases.

These values should be interpreted as descriptive results for the evaluated configurations and not as evidence of statistical equivalence or universal superiority of one approach.

## Reproducing the Experiments

### Requirements

The exact environment depends on the experimental branch. The main tools used in the study include:

- Python
- APKTool
- Java / JDK (`jarsigner`, `keytool`)
- Ollama for local LLM inference
- VirusTotal API v3


### Malware acquisition

Malware samples are not included. Use the SHA-256 identifiers in `data/android_malware_metadata.xlsx` to retrieve samples only if you have legitimate access to the relevant repositories and are authorized to handle malware.

### Raw results

The `results/` directories contain the raw or intermediate outputs used in the analysis. The LLM JSONL files include sample identifiers, assigned techniques, original and modified scores, VirusTotal statistics, and transformation metrics. Failed-sample CSV files record pipeline failures and the stage at which they occurred.

## Reproducibility Notes

To reproduce the paper as closely as possible, record and preserve:

- exact sample SHA-256 identifiers;
- model names and versions;
- Ollama version;
- APKTool version;
- prompt templates and technique-specific examples;
- suitability-score parameters and thresholds;
- context-window and temperature settings;
- VirusTotal scan date/time;
- raw VirusTotal verdict counts;
- transformation, validation, fallback, and rebuild outcomes.

Because VirusTotal engines and signatures change over time, rescanning the same APKs at a later date may not reproduce exactly the detection scores reported in the paper.

## Safety and Ethical Use

This repository is intended solely for **academic cybersecurity research and reproducibility**. It does not distribute malware binaries. All experiments should be conducted in an isolated and controlled environment. Do not execute malware on production systems or third-party infrastructure.


"# SmaliObfuscation" 
