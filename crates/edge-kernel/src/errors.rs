use std::fmt;

pub type EdgeResult<T> = Result<T, EdgeError>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EdgeErrorKind {
    InvalidArgument,
    NotFound,
    Unsupported,
    VersionMismatch,
    VerificationFailed,
    Storage,
    Internal,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EdgeError {
    pub kind: EdgeErrorKind,
    pub message: String,
}

impl EdgeError {
    pub fn new(kind: EdgeErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
        }
    }
}

impl fmt::Display for EdgeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}: {}", self.kind, self.message)
    }
}

impl std::error::Error for EdgeError {}

