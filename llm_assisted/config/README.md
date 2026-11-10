\# Experiment Configuration



This document reports the experimental configuration used for the Qwen2.5-Coder:14B and Mistral-Nemo:12B Smali-transformation experiments.



\## LLM Configuration



| Parameter | Value |

|---|---|

| Qwen model | `qwen2.5-coder:14b` |

| Mistral model | `mistral-nemo:12b` |

| Inference framework | Ollama |

| Ollama endpoint | `http://localhost:11434` |

| Context window | 8,192 tokens |

| Temperature | 0.1 |

| Request timeout | 300 s |

| Retries on error | 1 |

| Multi-method prompt budget | 6,000 characters |

| Maximum candidate-method size | 8,000 characters |



The corresponding configuration variables are:



```text

NUM\\\\\\\_CTX=8192

OLLAMA\\\\\\\_TIMEOUT=300

OLLAMA\\\\\\\_RETRY\\\\\\\_ATTEMPTS=1

MAX\\\\\\\_PROMPT\\\\\\\_CHARS=6000

MAX\\\\\\\_SINGLE\\\\\\\_METHOD\\\\\\\_CHARS=8000

```



Inference was executed locally. A temperature of 0.1 was used to reduce output variability because Smali transformations are subject to strict syntactic constraints.



\## Smali File Eligibility



Before suitability scoring, Smali files are filtered. A file is discarded when:



\- its size is below 100 characters; or

\- it contains fewer than one method and two `invoke-\\\\\\\*` instructions.



The following structural features are extracted from each candidate Smali file:



\- `string\\\\\\\_count`

\- `invoke\\\\\\\_count`

\- `branches\\\\\\\_count`

\- `method\\\\\\\_count`

\- `api\\\\\\\_diversity`

\- `has\\\\\\\_reflection`

\- `has\\\\\\\_network`

\- `has\\\\\\\_crypto`

\- `has\\\\\\\_file\\\\\\\_ops`

\- `has\\\\\\\_obfuscated`



Derived characteristics include, among others:



```text

string\\\\\\\_heavy          if string\\\\\\\_count > 5

complex\\\\\\\_control\\\\\\\_flow  if branches\\\\\\\_count > 5

already\\\\\\\_obfuscated    if has\\\\\\\_obfuscated == true

```



\## Suitability Scoring



For each file \\(f\\) and transformation technique \\(t\\), the pipeline computes a suitability score in the range `\\\\\\\[0,100]`:



```text

score(t, f) = base(f) + bonus(t, f)

```



\### Common base adjustments



| Condition | Score adjustment |

|---|---:|

| File size > 5,000 characters | +8 |

| File size > 50,000 characters | -10 |

| File already appears obfuscated | -15 |



\### Technique-specific scoring



\*\*String Obfuscation\*\*



\- contribution proportional to `string\\\\\\\_count`, up to 45 points;

\- contribution proportional to `invoke\\\\\\\_count`, up to 15 points;

\- additional bonuses for sensitive operations and high API diversity.



\*\*Dead Code Injection\*\*



\- contribution proportional to `invoke\\\\\\\_count`, up to 40 points;

\- contribution proportional to `branches\\\\\\\_count`, up to 20 points;

\- additional bonuses for API-heavy and multi-method files.



\*\*Opaque Predicates\*\*



\- contribution proportional to `branches\\\\\\\_count`, up to 45 points;

\- penalty of 20 points when fewer than two branches are present.



\*\*Benign Class Injection\*\*



\- base score of 50 for files containing network operations;

\- base score of 45 for cryptographic operations;

\- base score of 30 for file operations;

\- additional bonuses based on `invoke\\\\\\\_count` and API diversity.



\*\*Reflection Call\*\*



\- base score of 60 when reflection is already present;

\- otherwise, base score of 0;

\- additional bonuses based on `invoke\\\\\\\_count` and method count.





\## Suitability Threshold



The minimum suitability threshold is:





MIN\_SCORE\_THRESHOLD=30





A file is discarded when its maximum suitability score across all five techniques is below 30.



For each eligible file, the five technique scores are ranked in descending order. The pipeline initially attempts the highest-scoring technique, subject to balancing constraints.



\## Adaptive Number of Candidate Files



The number of candidate files depends on the number of Smali files in the application's main package:



| Files in main package | Files selected |

|---:|---:|

| < 10 | 2 |

| < 30 | 3 |

| < 80 | 6 |

| < 200 | 8 |

| >= 200 | 10 |



The maximum number of selected files is capped at 10.



\## Fallback Order



If the initially assigned transformation fails because of an empty LLM response, validation failure, or timeout, the pipeline attempts alternative transformations according to the following fixed order:



```text

String Obfuscation

\\\&#x20;   -> Opaque Predicates

\\\&#x20;   -> Dead Code Injection

\\\&#x20;   -> Benign Class Injection

\\\&#x20;   -> Reflection Call

```





\## Prompt Construction



For each `(file, technique)` pair, the pipeline constructs a prompt containing:



1\. a system instruction defining the model as a Smali-bytecode transformer;

2\. a `SMALI\\\\\\\_CONSTRAINTS` block;

3\. a technique-specific input/output example;

4\. the selected Smali method or methods to transform.



The complete Smali file is not sent to the model. Only methods selected as suitable for the assigned technique are included.



Technique-specific priorities are:



| Technique | Primary selection criterion |

|---|---|

| String Obfuscation | `const-string` count |

| Dead Code Injection | `invoke-\\\\\\\*` count |

| Opaque Predicates | `if-\\\\\\\*` count |

| Benign Class Injection | network/crypto references |

| Reflection Call | `invoke-virtual` / `invoke-interface` count |



String Obfuscation, Dead Code Injection, and Reflection Call operate on individual methods. Up to three eligible methods are attempted in increasing-size order.



Opaque Predicates and Benign Class Injection operate in batch mode, processing multiple selected methods within the 6,000-character prompt budget.

