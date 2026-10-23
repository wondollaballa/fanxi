//! Errors shared by the launcher's Rust core and its Tauri commands.
//!
//! Commands return a structured error object rather than a formatted string so the UI can tell an
//! expired session (`status == 401`) from a server that is simply offline.

use serde::ser::SerializeStruct;
use serde::{Serialize, Serializer};

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("{message}")]
    Api {
        status: u16,
        code: String,
        message: String,
    },
    #[error("{0}")]
    Network(String),
    #[error("{0}")]
    Control(String),
    #[error("{0}")]
    Game(String),
    #[error("{0}")]
    Config(String),
    #[error("{0}")]
    Io(String),
    #[error("{0}")]
    Json(String),
    #[error("{0}")]
    Validation(String),
}

impl AppError {
    pub fn api(status: u16, code: impl Into<String>, message: impl Into<String>) -> Self {
        Self::Api {
            status,
            code: code.into(),
            message: message.into(),
        }
    }

    pub fn kind(&self) -> &'static str {
        match self {
            Self::Api { .. } => "api",
            Self::Network(_) => "network",
            Self::Control(_) => "control",
            Self::Game(_) => "game",
            Self::Config(_) => "config",
            Self::Io(_) => "io",
            Self::Json(_) => "json",
            Self::Validation(_) => "validation",
        }
    }

    pub fn status(&self) -> Option<u16> {
        match self {
            Self::Api { status, .. } => Some(*status),
            _ => None,
        }
    }

    pub fn code(&self) -> Option<&str> {
        match self {
            Self::Api { code, .. } => Some(code.as_str()),
            _ => None,
        }
    }
}

impl From<std::io::Error> for AppError {
    fn from(value: std::io::Error) -> Self {
        Self::Io(value.to_string())
    }
}

impl From<serde_json::Error> for AppError {
    fn from(value: serde_json::Error) -> Self {
        Self::Json(value.to_string())
    }
}

impl From<reqwest::Error> for AppError {
    fn from(value: reqwest::Error) -> Self {
        if value.is_timeout() {
            return Self::Network("the server took too long to answer".to_string());
        }
        if value.is_connect() {
            return Self::Network("cannot reach the server; is it running?".to_string());
        }
        Self::Network(value.to_string())
    }
}

impl Serialize for AppError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut state = serializer.serialize_struct("CommandError", 4)?;
        state.serialize_field("kind", self.kind())?;
        state.serialize_field("message", &self.to_string())?;
        if let Some(status) = self.status() {
            state.serialize_field("status", &status)?;
        }
        if let Some(code) = self.code() {
            state.serialize_field("code", code)?;
        }
        state.end()
    }
}

pub type AppResult<T> = Result<T, AppError>;
