export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL || "http://10.0.2.2:8000";

function buildUrl(path) {
  if (!path) return API_BASE_URL;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return `${API_BASE_URL}${path}`;
  return `${API_BASE_URL}/${path}`;
}

async function parseJsonResponse(response) {
  let json = null;
  try {
    json = await response.json();
  } catch {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return {};
  }

  if (!response.ok) {
    const detail = json?.detail || json?.message || `HTTP ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return json;
}

export async function apiGet(path) {
  const response = await fetch(buildUrl(path), {
    method: "GET",
  });
  return parseJsonResponse(response);
}

export async function apiPostJson(path, payload) {
  const response = await fetch(buildUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload || {}),
  });
  return parseJsonResponse(response);
}

export async function apiUploadFile(path, asset) {
  const formData = new FormData();
  const filename =
    asset?.fileName || `upload_${Date.now()}.${asset?.uri?.endsWith(".png") ? "png" : "jpg"}`;
  const mimeType = asset?.mimeType || "image/jpeg";

  formData.append("file", {
    uri: asset.uri,
    name: filename,
    type: mimeType,
  });

  const response = await fetch(buildUrl(path), {
    method: "POST",
    body: formData,
  });

  return parseJsonResponse(response);
}

