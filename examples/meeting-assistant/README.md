# Canonical Reference Example: Meeting Assistant

Demonstrates the evidence-driven Model Adaptation workflow in `slm`:

```text
examples/meeting-assistant/
├── slm.yaml
├── data/
│   ├── train.jsonl
│   └── eval.jsonl
└── schema/
    └── output.json
```

---

## Developer Workflow

### 1. Read-Only Dataset Inspection
```bash
slm data-inspect examples/meeting-assistant/data/train.jsonl --eval examples/meeting-assistant/data/eval.jsonl --schema examples/meeting-assistant/schema/output.json
```

### 2. Immutable Dataset Preparation & Snapshot
```bash
slm prepare examples/meeting-assistant/data/train.jsonl --output examples/meeting-assistant
```

### 3. Measure Pre-Adaptation Baselines
```bash
slm baseline examples/meeting-assistant/data/train.jsonl --task meeting.action_detection
```

### 4. Compile Evidence-Driven Adaptation Plan
```bash
slm plan --project examples/meeting-assistant
```

### 5. Run Project Diagnostics & Health Check
```bash
slm doctor --project examples/meeting-assistant
```
