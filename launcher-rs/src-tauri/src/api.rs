//! HTTP client for the Fanxi server. This mirrors `launcher/fanxi_launcher/api.py`, including the
//! stable error envelope: `{"error": {"code": "...", "message": "..."}}`.

use std::time::Duration;

use reqwest::{Client, Method, Response};
use serde_json::{Value, json};

use crate::error::{AppError, AppResult};

const VERSION: &str = env!("CARGO_PKG_VERSION");
const TIMEOUT_SECS: u64 = 15;

#[derive(Clone)]
pub struct ApiClient {
    base: String,
    client: Client,
}

impl ApiClient {
    pub fn new(base_url: &str, insecure: bool) -> AppResult<Self> {
        let base = normalize_base(base_url);
        let mut builder = Client::builder()
            .timeout(Duration::from_secs(TIMEOUT_SECS))
            .user_agent(format!("FanxiLauncher/{VERSION}"));
        if insecure {
            builder = builder.danger_accept_invalid_certs(true);
        }
        let client = builder
            .build()
            .map_err(|error| AppError::Network(error.to_string()))?;
        Ok(Self { base, client })
    }

    pub fn base(&self) -> &str {
        &self.base
    }

    pub fn api_root(&self) -> String {
        format!("{}/api/v1", self.base)
    }

    pub async fn status(&self) -> AppResult<Value> {
        self.request(Method::GET, "/status", None, None, None).await
    }

    pub async fn news(&self, limit: u32) -> AppResult<Vec<Value>> {
        let value = self
            .request(
                Method::GET,
                "/news",
                None,
                None,
                Some(vec![("limit".to_string(), limit.to_string())]),
            )
            .await?;
        Ok(value
            .get("news")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default())
    }

    pub async fn register(
        &self,
        username: &str,
        password: &str,
        email: Option<&str>,
    ) -> AppResult<Value> {
        let body = json!({
            "username": username,
            "password": password,
            "email": email.filter(|value| !value.trim().is_empty()),
        });
        self.request(Method::POST, "/auth/register", Some(body), None, None)
            .await
    }

    pub async fn login(&self, username: &str, password: &str) -> AppResult<Value> {
        let body = json!({"username": username, "password": password});
        self.request(Method::POST, "/auth/login", Some(body), None, None)
            .await
    }

    pub async fn logout(&self, token: &str) -> AppResult<()> {
        self.request(Method::POST, "/auth/logout", None, Some(token), None)
            .await?;
        Ok(())
    }

    pub async fn me(&self, token: &str) -> AppResult<Value> {
        self.request(Method::GET, "/me", None, Some(token), None)
            .await
    }

    pub async fn characters(&self, token: &str) -> AppResult<Vec<Value>> {
        let value = self
            .request(Method::GET, "/characters", None, Some(token), None)
            .await?;
        Ok(value
            .get("characters")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default())
    }

    pub async fn create_character(&self, token: &str, data: Value) -> AppResult<Value> {
        let value = self
            .request(Method::POST, "/characters", Some(data), Some(token), None)
            .await?;
        Ok(value.get("character").cloned().unwrap_or(value))
    }

    pub async fn save_character_design(
        &self,
        token: &str,
        character_id: i64,
        data: Value,
    ) -> AppResult<Value> {
        let value = self
            .request(
                Method::PATCH,
                &format!("/characters/{character_id}/design"),
                Some(data),
                Some(token),
                None,
            )
            .await?;
        Ok(value.get("character").cloned().unwrap_or(value))
    }

    /// The Data page snapshot: merits, gil, mastery rank, home points, currencies and the
    /// Armory history for one character.
    pub async fn character_data(&self, token: &str, character_id: i64) -> AppResult<Value> {
        self.request(
            Method::GET,
            &format!("/characters/{character_id}/data"),
            None,
            Some(token),
            None,
        )
        .await
    }

    /// Run one Data page action.  Every endpoint returns the refreshed snapshot, except the
    /// Armory, which returns `{ item, data }`.
    pub async fn character_action(
        &self,
        token: &str,
        character_id: i64,
        action: &str,
        body: Value,
    ) -> AppResult<Value> {
        self.request(
            Method::POST,
            &format!("/characters/{character_id}/{action}"),
            Some(body),
            Some(token),
            None,
        )
        .await
    }

    /// The Warps page snapshot: the character's saved places, the slot limit and the next
    /// auto-increment number.
    pub async fn character_warps(&self, token: &str, character_id: i64) -> AppResult<Value> {
        self.request(
            Method::GET,
            &format!("/characters/{character_id}/warps"),
            None,
            Some(token),
            None,
        )
        .await
    }

    pub async fn mark_character_warp(
        &self,
        token: &str,
        character_id: i64,
        body: Value,
    ) -> AppResult<Value> {
        self.request(
            Method::POST,
            &format!("/characters/{character_id}/warps"),
            Some(body),
            Some(token),
            None,
        )
        .await
    }

    pub async fn rename_character_warp(
        &self,
        token: &str,
        character_id: i64,
        slot: i64,
        alias: Option<String>,
    ) -> AppResult<Value> {
        self.request(
            Method::PATCH,
            &format!("/characters/{character_id}/warps/{slot}"),
            Some(json!({"alias": alias.unwrap_or_default()})),
            Some(token),
            None,
        )
        .await
    }

    pub async fn delete_character_warp(
        &self,
        token: &str,
        character_id: i64,
        slot: i64,
    ) -> AppResult<Value> {
        self.request(
            Method::DELETE,
            &format!("/characters/{character_id}/warps/{slot}"),
            None,
            Some(token),
            None,
        )
        .await
    }

    pub async fn search_armory(
        &self,
        token: &str,
        character_id: i64,
        query: &str,
        kind: Option<&str>,
    ) -> AppResult<Value> {
        let mut params = vec![
            ("q".to_string(), query.to_string()),
            ("limit".to_string(), "40".to_string()),
        ];
        if let Some(kind) = kind.filter(|value| !value.is_empty()) {
            params.push(("kind".to_string(), kind.to_string()));
        }
        self.request(
            Method::GET,
            &format!("/characters/{character_id}/items/search"),
            None,
            Some(token),
            Some(params),
        )
        .await
    }

    pub async fn launch(&self, token: &str, character_id: Option<i64>) -> AppResult<Value> {
        self.request(
            Method::POST,
            "/launch",
            Some(json!({"character_id": character_id})),
            Some(token),
            None,
        )
        .await
    }

    pub async fn sub_accounts(&self, token: &str) -> AppResult<Value> {
        self.request(Method::GET, "/accounts/sub", None, Some(token), None)
            .await
    }

    pub async fn create_sub(&self, token: &str, character: Option<Value>) -> AppResult<Value> {
        let body = match character {
            Some(character) => json!({"character": character}),
            None => json!({}),
        };
        self.request(Method::POST, "/accounts/sub", Some(body), Some(token), None)
            .await
    }

    pub async fn activate_sub(&self, token: &str, sub_id: i64) -> AppResult<Value> {
        let value = self
            .request(
                Method::PATCH,
                &format!("/accounts/sub/{sub_id}"),
                Some(json!({"status": "active"})),
                Some(token),
                None,
            )
            .await?;
        Ok(value.get("sub").cloned().unwrap_or(value))
    }

    pub async fn create_sub_character(
        &self,
        token: &str,
        sub_id: i64,
        data: Value,
    ) -> AppResult<Value> {
        let value = self
            .request(
                Method::POST,
                &format!("/accounts/sub/{sub_id}/characters"),
                Some(json!({"character": data})),
                Some(token),
                None,
            )
            .await?;
        Ok(value.get("character").cloned().unwrap_or(value))
    }

    pub async fn launch_sub(
        &self,
        token: &str,
        sub_id: i64,
        character_id: Option<i64>,
    ) -> AppResult<Value> {
        self.request(
            Method::POST,
            &format!("/accounts/sub/{sub_id}/launch"),
            Some(json!({"character_id": character_id})),
            Some(token),
            None,
        )
        .await
    }

    pub async fn delete_sub(&self, token: &str, sub_id: i64, purge: bool) -> AppResult<Value> {
        let query = if purge {
            Some(vec![("purge".to_string(), "1".to_string())])
        } else {
            None
        };
        self.request(
            Method::DELETE,
            &format!("/accounts/sub/{sub_id}"),
            None,
            Some(token),
            query,
        )
        .await
    }

    async fn request(
        &self,
        method: Method,
        path: &str,
        body: Option<Value>,
        token: Option<&str>,
        query: Option<Vec<(String, String)>>,
    ) -> AppResult<Value> {
        let url = format!("{}{}", self.api_root(), path);
        let mut request = self
            .client
            .request(method, &url)
            .header("Accept", "application/json");
        if let Some(token) = token {
            request = request.bearer_auth(token);
        }
        if let Some(query) = query {
            request = request.query(&query);
        }
        if let Some(body) = body {
            request = request.json(&body);
        }

        let response = request
            .send()
            .await
            .map_err(|error| network_error(error, &self.base))?;
        decode_response(response).await
    }
}

async fn decode_response(response: Response) -> AppResult<Value> {
    let status = response.status();
    let body = response
        .bytes()
        .await
        .map_err(|error| AppError::Network(error.to_string()))?;
    if !status.is_success() {
        let (code, message) = parse_error(&body).unwrap_or_else(|| {
            (
                "http_error".to_string(),
                status
                    .canonical_reason()
                    .unwrap_or("the server refused the request")
                    .to_string(),
            )
        });
        return Err(AppError::api(status.as_u16(), code, message));
    }
    if body.is_empty() {
        return Ok(Value::Null);
    }
    serde_json::from_slice(&body).map_err(|error| {
        AppError::Network(format!(
            "the server sent something that is not JSON: {error}"
        ))
    })
}

fn parse_error(body: &[u8]) -> Option<(String, String)> {
    let value: Value = serde_json::from_slice(body).ok()?;
    let error = value.get("error")?;
    let code = error
        .get("code")
        .and_then(Value::as_str)
        .unwrap_or("http_error")
        .to_string();
    let message = error
        .get("message")
        .and_then(Value::as_str)
        .unwrap_or("the server refused the request")
        .to_string();
    Some((code, message))
}

fn normalize_base(base_url: &str) -> String {
    let mut base = base_url.trim().trim_end_matches('/').to_string();
    if base.is_empty() {
        base = crate::config::DEFAULT_API.to_string();
    }
    if let Some(stripped) = base.strip_suffix("/api/v1") {
        base = stripped.trim_end_matches('/').to_string();
    }
    if !base.starts_with("http://") && !base.starts_with("https://") {
        base = format!("http://{base}");
    }
    base
}

fn network_error(error: reqwest::Error, base: &str) -> AppError {
    if error.is_timeout() {
        return AppError::Network(format!(
            "the Fanxi server at {base} took too long to answer"
        ));
    }
    if error.is_connect() {
        return AppError::Network(format!("cannot reach {base}: is the Fanxi server running?"));
    }
    AppError::Network(format!("cannot reach {base}: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base_normalisation_accepts_common_forms() {
        assert_eq!(normalize_base("127.0.0.1:8080"), "http://127.0.0.1:8080");
        assert_eq!(
            normalize_base("https://fanxi.example.com/api/v1/"),
            "https://fanxi.example.com"
        );
        assert_eq!(
            normalize_base("http://127.0.0.1:8080/"),
            "http://127.0.0.1:8080"
        );
    }
}
