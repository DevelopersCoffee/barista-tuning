#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DecisionKind {
    Choice,
    Score,
    Boolean,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Probability {
    pub option: String,
    pub probability: f32,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ChoiceResult {
    pub selected: String,
    pub probabilities: Vec<Probability>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ScoreResult {
    pub value: f32,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BooleanResult {
    pub probability: f32,
}

#[derive(Debug, Clone, PartialEq)]
pub enum DecisionOutput {
    Choice(ChoiceResult),
    Score(ScoreResult),
    Boolean(BooleanResult),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DecisionStatus {
    Accepted,
    Abstained,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DecisionResult {
    pub output: DecisionOutput,
    pub confidence: f32,
    pub status: DecisionStatus,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EscalationTarget {
    IntentModel,
    GenerativeModel,
    Human,
    Reject,
}

#[derive(Debug, Clone, PartialEq)]
pub struct EscalationPolicy {
    pub threshold: f32,
    pub target: EscalationTarget,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecisionQuestion {
    pub id: String,
    pub kind: DecisionKind,
    pub options: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecisionInput {
    pub question: DecisionQuestion,
    pub payload: String,
}
