# Prompt Templates

## Reproducibility Note

The experimental pipeline constructs a two-part prompt for each `(Smali file, transformation technique)` pair: a system prompt and a user prompt.


## 1. Prompt Structure

For every `(file, technique)` pair, the pipeline constructs two prompt components.

### System Prompt

The system prompt defines the model as a Smali-bytecode transformer and enforces the following core requirements:

- output only Smali code;
- do not modify try-catch labels;
- do not use registers beyond the limit declared in `.locals`;
- do not reference undefined labels;
- do not remove, modify, or reorder existing instructions;
- when uncertain, leave the method unchanged.

### User Prompt

The user prompt contains three elements, in this order:

1. the common `SMALI_CONSTRAINTS` block;
2. a technique-specific transformation example;
3. the Smali code selected for transformation.

The general structure is:

```text
[SMALI_CONSTRAINTS]

[TECHNIQUE-SPECIFIC EXAMPLE]

[SELECTED SMALI CODE]
```

Only the methods selected for the assigned transformation are included in the prompt. The complete Smali file is not provided to the model.

---

## 2. Common SMALI_CONSTRAINTS

The following constraints are included in the user prompt:

```text
Do not modify try-catch labels
(:try_start_X, :try_end_X, :catch_X, :catchall_X).

Do not use registers beyond the declared .locals limit.

Every added label must be both defined and referenced
inside the same method.

Do not add .catch or .catchall directives.

Do not modify the method signature or .locals/.registers directives.

Do not remove or reorder existing instructions;
only insertion of new instructions is permitted.

Do not alter the method return type or return value.

Do not insert instructions between filled-array-data,
packed-switch, or sparse-switch directives and their data blocks.

Use only valid Dalvik opcodes.

Return the complete method from .method to .end method.

The modified method must be at least as long as the original method.
```

The reduced file header used for prompting retains only:

```text
.class
.super
.implements
.source
```

Fields and annotation blocks are excluded from the prompt and later restored when the transformed method is merged into the complete original file.

---

# 3. Technique-Specific Prompt Material

## 3.1 String Obfuscation

### Selection

Methods are prioritized according to their number of `const-string` instructions. Eligible methods must contain at least two `const-string` instructions.

String Obfuscation operates on one method per LLM request.

### Transformation Objective

String constants are replaced with Base64-encoded values followed by a decoding call. The decoded value is stored back in the original register.

### Example

```smali
# Before:
const-string v0, "http://evil.com/api"

# After:
const-string v0, "aHR0cDovL2V2aWwuY29tL2FwaQ=="
invoke-static {v0}, Lcom/util/Decode;->b64(Ljava/lang/String;)Ljava/lang/String;
move-result-object v0
```

### Prompt Template Structure

```text
[SMALI_CONSTRAINTS]

Apply String Obfuscation to the supplied Smali method.

[STRING OBFUSCATION EXAMPLE]

[SELECTED SMALI METHOD]
```

---

## 3.2 Dead Code Injection

### Selection

Methods are prioritized according to their number of `invoke-*` instructions. Eligible methods must contain at least three invoke instructions.

Dead Code Injection operates on one method per LLM request.

### Transformation Objective

Insert unreachable instructions while preserving the original execution flow. Injected dead blocks are skipped through a `goto`. Added labels use the `:lbl_dead_` and `:lbl_real_` prefixes.

### Example 
```smali
invoke-static {}, Ljava/lang/System;->currentTimeMillis()J
goto :lbl_real_0

:lbl_dead_0
const/4 v0, 0x0
if-nez v0, :lbl_dead_0

:lbl_real_0
return-void
```

### Prompt Template Structure

```text
[SMALI_CONSTRAINTS]

Apply Dead Code Injection to the supplied Smali method.

[DEAD CODE INJECTION EXAMPLE]

[SELECTED SMALI METHOD]
```

---

## 3.3 Opaque Predicates

### Selection

Methods are prioritized according to their number of `if-*` instructions.

Opaque Predicates operate in batch mode, allowing multiple selected methods to be included within the prompt-size limit.

### Transformation Objective

Introduce branches whose runtime result is predetermined while appearing as additional control-flow decisions to static analysis. Added labels use the `:op_` prefix.

### Example 

```smali
const/4 v0, 0x0
mul-int/lit8 v0, v0, 0x0   # v0 is always 0
if-nez v0, :op_dead_0       # never taken

# ... real code, always executed ...

goto :op_skip_0

:op_dead_0
const/4 v0, 0x1

:op_skip_0
```

### Prompt Template Structure

```text
[SMALI_CONSTRAINTS]

Apply Opaque Predicates to the supplied Smali methods.

[OPAQUE PREDICATES EXAMPLE]

[SELECTED SMALI METHODS]
```

---

## 3.4 Benign Class Injection

### Selection

Methods are prioritized according to network and cryptographic references.

Benign Class Injection operates in batch mode.

### Transformation Objective

Add calls to synthetic static utility methods with benign-looking names, such as:

```text
Lcom/android/utils/SystemHelper;
Lcom/util/AppLogger;
```

Example method names include:

```text
logEvent
loadConfig
checkPermission
```

### Example

```smali
const-string v0, "init"
invoke-static {v0}, Lcom/android/utils/SystemHelper;->logEvent(Ljava/lang/String;)V

# Original instruction, unchanged:
invoke-virtual {v2}, Landroid/telephony/TelephonyManager;->getDeviceId()Ljava/lang/String;
```

### Prompt Template Structure

```text
[SMALI_CONSTRAINTS]

Apply Benign Class Injection to the supplied Smali methods.

[BENIGN CLASS INJECTION EXAMPLE]

[SELECTED SMALI METHODS]
```

---

## 3.5 Reflection Call

### Selection

Methods are prioritized according to their number of:

```text
invoke-virtual
invoke-interface
```

The transformation operates on one method per LLM request.

Reflection Call requires additional free registers to construct the `forName` / `getMethod` / `invoke` sequence. Constructors invoked through `invoke-direct <init>` are excluded.

### Transformation Objective

Replace selected direct API calls with reflective invocations based on `java.lang.reflect.Method`.

### Example 

```smali
# Before:
invoke-virtual {v1}, Landroid/telephony/TelephonyManager;->getDeviceId()Ljava/lang/String;
move-result-object v0

# After (abbreviated):
const-string v3, "android.telephony.TelephonyManager"
invoke-static {v3}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;
move-result-object v4

const-string v5, "getDeviceId"

...

invoke-virtual {v7, v1, v8}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;
move-result-object v0
check-cast v0, Ljava/lang/String;
```


### Prompt Template Structure

```text
[SMALI_CONSTRAINTS]

Apply Reflection Call transformation to the supplied Smali method.

[REFLECTION CALL EXAMPLE]

[SELECTED SMALI METHOD]
```

---

# 4. Per-Method and Batch Prompting

The techniques operate in two different modes.

### Per-method mode

The following transformations process one method per LLM call:

- String Obfuscation;
- Dead Code Injection;
- Reflection Call.

Up to three eligible methods are attempted in increasing-size order before the transformation is considered unsuccessful.

### Batch mode

The following transformations may process multiple methods in the same prompt:

- Opaque Predicates;
- Benign Class Injection.

Selected methods are included up to the configured multi-method prompt budget.

---

# 5. Prompt-Size Limits

The experimental configuration uses:

```text
MAX_PROMPT_CHARS = 6000
MAX_SINGLE_METHOD_CHARS = 8000
NUM_CTX = 8192
```

The 6,000-character limit applies to multi-method prompt construction. The 8,000-character threshold is used to determine eligibility for transformations operating on individual methods.

---

