import { useEffect, useState } from "react";

import {
  bootstrapLocal,
  createCredential,
  createRuntime,
  getAssetDownload,
  getSystemStatus,
  listAssets,
  testRuntime,
  uploadAsset,
  type AssetRecord,
  type LocalBootstrap,
  type SystemStatus,
} from "./api";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected integration error";
}

export function IntegrationLab() {
  const [bootstrap, setBootstrap] = useState<LocalBootstrap | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [assets, setAssets] = useState<AssetRecord[]>([]);
  const [provider, setProvider] = useState("deepseek");
  const [modelId, setModelId] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [runtimeResult, setRuntimeResult] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ownerId = bootstrap?.users.find((user) => user.is_host)?.id;

  const refresh = async () => {
    const [nextBootstrap, nextStatus] = await Promise.all([bootstrapLocal(), getSystemStatus()]);
    setBootstrap(nextBootstrap);
    setStatus(nextStatus);
    const hostId = nextBootstrap.users.find((user) => user.is_host)?.id;
    if (hostId) setAssets(await listAssets(hostId));
  };

  useEffect(() => {
    refresh().catch((reason) => setError(messageOf(reason)));
  }, []);

  const upload = async (file: File | undefined) => {
    if (!file || !ownerId) return;
    setBusy("asset");
    setError(null);
    try {
      await uploadAsset(ownerId, file);
      setAssets(await listAssets(ownerId));
      setStatus(await getSystemStatus());
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(null);
    }
  };

  const openAsset = async (assetId: string) => {
    if (!ownerId) return;
    try {
      const download = await getAssetDownload(assetId, ownerId);
      window.open(download.url, "_blank", "noopener,noreferrer");
    } catch (reason) {
      setError(messageOf(reason));
    }
  };

  const saveAndTestRuntime = async () => {
    if (!ownerId || !modelId.trim() || !apiSecret.trim()) return;
    setBusy("runtime");
    setError(null);
    setRuntimeResult(null);
    try {
      const credential = await createCredential(ownerId, provider, `${provider} local test`, apiSecret.trim());
      setApiSecret("");
      const runtime = await createRuntime(ownerId, {
        display_name: `${provider} · ${modelId.trim()}`,
        provider,
        model_id: modelId.trim(),
        credential_id: credential.id,
        temperature: 0.2,
      });
      setRuntimeResult(await testRuntime(ownerId, runtime.id));
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="integration-shell">
      <header className="integration-heading">
        <div>
          <p className="eyebrow">Local integration lab</p>
          <h2>Verify database, object storage, and a real AI runtime.</h2>
          <p>Secrets are submitted to the backend, encrypted, masked, and never returned to this page.</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={Boolean(busy)}>Refresh status</button>
      </header>

      {error && <p className="integration-error">{error}</p>}

      <div className="integration-grid">
        <article className="integration-card">
          <p className="note-label">PostgreSQL</p>
          <h3>{status?.database.reachable ? "Connected" : "Not connected"}</h3>
          <dl>
            <div><dt>Dialect</dt><dd>{status?.database.dialect ?? "—"}</dd></div>
            <div><dt>Environment</dt><dd>{status?.app_env ?? "—"}</dd></div>
            <div><dt>Credential key</dt><dd>{status?.credential_encryption.persistent_key_configured ? "Persistent" : "Ephemeral"}</dd></div>
          </dl>
        </article>

        <article className="integration-card">
          <p className="note-label">R2-compatible storage</p>
          <h3>{status?.object_storage.reachable ? "Connected" : status?.object_storage.configured ? "Configured, unreachable" : "Not configured"}</h3>
          <p>{status?.object_storage.bucket ?? "No bucket selected"}</p>
          <label className="file-control">
            Upload test asset
            <input type="file" disabled={!ownerId || busy === "asset"} onChange={(event) => void upload(event.target.files?.[0])} />
          </label>
          <ul className="asset-list">
            {assets.map((asset) => <li key={asset.id}>
              <span>{asset.filename}<small>{asset.status} · {asset.size_bytes ?? 0} bytes</small></span>
              {asset.status === "ready" && <button type="button" onClick={() => void openAsset(asset.id)}>Open signed URL</button>}
            </li>)}
            {assets.length === 0 && <li>No uploaded assets yet.</li>}
          </ul>
        </article>

        <article className="integration-card runtime-lab">
          <p className="note-label">Real AI provider</p>
          <h3>Create, encrypt, and test a runtime</h3>
          <label>Provider<select value={provider} onChange={(event) => setProvider(event.target.value)}>
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="openai_compatible">OpenAI-compatible endpoint</option>
          </select></label>
          <label>Model ID<input value={modelId} onChange={(event) => setModelId(event.target.value)} placeholder="Use a model available to your account" /></label>
          <label>API key<input type="password" autoComplete="off" value={apiSecret} onChange={(event) => setApiSecret(event.target.value)} placeholder="Stored encrypted by the backend" /></label>
          <button type="button" disabled={!ownerId || !modelId.trim() || !apiSecret.trim() || busy === "runtime"} onClick={() => void saveAndTestRuntime()}>
            {busy === "runtime" ? "Calling provider…" : "Save credential & test decision"}
          </button>
          {runtimeResult && <pre>{JSON.stringify(runtimeResult, null, 2)}</pre>}
        </article>
      </div>
    </section>
  );
}
