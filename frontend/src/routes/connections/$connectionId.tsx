import {
  createRoute,
  redirect,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import type { AuthContextValue } from "@/features/auth/AuthProvider";
import { ConnectionCard } from "@/features/connections/ConnectionCard";
import {
  useConnections,
  useRemoveConnection,
  useUpdateConnection,
} from "@/features/connections/useConnections";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { connectionsApi, type SyncRun } from "@/api/connections";
import { rootRoute } from "../__root";

export const connectionDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/connections/$connectionId",
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: "/login" });
  },
  component: ConnectionDetailPage,
});

const SYNC_INTERVAL_OPTIONS = [
  { value: "15m", label: "Every 15 minutes" },
  { value: "1h", label: "Every hour" },
  { value: "6h", label: "Every 6 hours" },
  { value: "1d", label: "Daily" },
  { value: "manual", label: "Manual only" },
];

const AUTH_MODE_OPTIONS = [
  { value: "none", label: "None" },
  { value: "api_key", label: "API Key" },
  { value: "bearer", label: "Bearer token" },
  { value: "basic", label: "Basic auth" },
];

// Statuses that mean the run is still in flight — keep polling.
const PENDING_STATUSES = new Set(["queued", "running"]);
const POLL_INTERVAL_MS = 2_000;
const POLL_MAX_ATTEMPTS = 15; // ~30 s cap

function SyncRunFeedback({
  connectionId,
  pollResetKey,
}: {
  connectionId: string;
  pollResetKey: number;
}) {
  // Count how many fetches have fired since the last poll reset.
  const attemptRef = useRef(0);

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ["sync-runs", connectionId],
    queryFn: async () => {
      attemptRef.current += 1;
      return connectionsApi.syncRuns(connectionId);
    },
    staleTime: 10_000,
    refetchOnWindowFocus: false,
    refetchInterval: (query): number | false => {
      const latest = (query.state.data as SyncRun[] | undefined)?.[0];
      const isPending = !latest || PENDING_STATUSES.has(latest.status);
      const underCap = attemptRef.current < POLL_MAX_ATTEMPTS;
      return isPending && underCap ? POLL_INTERVAL_MS : false;
    },
  });

  // Reset attempt counter whenever the parent kicks a new poll cycle.
  // Using a ref mutation inside render is intentional here: we only want to
  // reset the counter when pollResetKey changes, not trigger a re-render.
  const prevKeyRef = useRef(pollResetKey);
  if (prevKeyRef.current !== pollResetKey) {
    prevKeyRef.current = pollResetKey;
    attemptRef.current = 0;
  }

  if (isLoading) {
    return <Skeleton className="h-20 w-full" />;
  }

  const latest = runs[0];
  if (!latest) {
    return (
      <p className="text-sm text-muted-foreground">No sync runs yet.</p>
    );
  }

  const isPending = PENDING_STATUSES.has(latest.status);
  const isError = latest.status === "failed";

  return (
    <div
      className={`rounded-lg border p-3 text-sm space-y-1 ${
        isError
          ? "border-destructive/30 bg-destructive/10"
          : "border-border bg-muted/30"
      }`}
    >
      <p className={`font-medium ${isError ? "text-destructive" : "text-foreground"}`}>
        Last sync:{" "}
        {isPending ? (
          <span className="text-muted-foreground">{latest.status}&hellip;</span>
        ) : (
          latest.status
        )}
      </p>
      {!isError && !isPending && (
        <p className="text-muted-foreground">
          {latest.accounts_synced ?? 0} account
          {(latest.accounts_synced ?? 0) !== 1 ? "s" : ""},{" "}
          {latest.transactions_synced ?? 0} transaction
          {(latest.transactions_synced ?? 0) !== 1 ? "s" : ""} imported.
        </p>
      )}
      {isError && (
        <p className="text-destructive">
          {latest.error_code ?? "unknown error"}
          {latest.error_detail
            ? `: ${JSON.stringify(latest.error_detail)}`
            : ""}
        </p>
      )}
      {latest.completed_at && (
        <p className="text-xs text-muted-foreground">
          Completed {new Date(latest.completed_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}

function ConnectionDetailPage() {
  const { connectionId } = useParams({ from: "/connections/$connectionId" });
  const { data = [] } = useConnections();
  const connection = data.find((item) => item.id === connectionId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const remove = useRemoveConnection();
  const update = useUpdateConnection();

  const [removeOpen, setRemoveOpen] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const [editOpen, setEditOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editSource, setEditSource] = useState("");
  const [editAuthMode, setEditAuthMode] = useState("none");
  const [editSyncInterval, setEditSyncInterval] = useState("1h");
  const [editError, setEditError] = useState<string | null>(null);

  const [syncingNow, setSyncingNow] = useState(false);
  const [syncNowError, setSyncNowError] = useState<string | null>(null);
  // Incrementing this resets the poll-attempt counter inside SyncRunFeedback.
  const [syncPollKey, setSyncPollKey] = useState(0);

  const isFileProvider = connection?.provider_type === "json";

  const openEdit = () => {
    if (!connection) return;
    setEditName(connection.display_name ?? "");
    const cfg = connection.config ?? {};
    setEditSource(
      (cfg.url as string | undefined) ?? (cfg.path as string | undefined) ?? "",
    );
    setEditAuthMode((cfg.auth_mode as string | undefined) ?? "none");
    setEditSyncInterval((cfg.sync_interval as string | undefined) ?? "1h");
    setEditError(null);
    setEditOpen(true);
  };

  const handleEdit = () => {
    if (!connection) return;
    setEditError(null);

    const payload: { display_name?: string | null; config?: Record<string, unknown> } = {};
    if (editName !== (connection.display_name ?? "")) {
      payload.display_name = editName || null;
    }

    if (isFileProvider) {
      const isUrl =
        editSource.startsWith("http://") || editSource.startsWith("https://");
      const newConfig: Record<string, unknown> = {
        ...connection.config,
        auth_mode: editAuthMode === "none" ? undefined : editAuthMode,
        sync_interval: editSyncInterval,
      };
      delete newConfig.url;
      delete newConfig.path;
      if (isUrl) {
        newConfig.url = editSource;
      } else if (editSource) {
        newConfig.path = editSource;
      }
      payload.config = newConfig;
    }

    update.mutate(
      { connectionId: connection.id, payload },
      {
        onSuccess: () => setEditOpen(false),
        onError: () => setEditError("Failed to update connection. Please try again."),
      },
    );
  };

  const handleSyncNow = async () => {
    if (!connection) return;
    setSyncingNow(true);
    setSyncNowError(null);
    try {
      await connectionsApi.sync(connection.id);
      setSyncPollKey((k) => k + 1);
      await queryClient.invalidateQueries({ queryKey: ["sync-runs", connection.id] });
      await queryClient.invalidateQueries({ queryKey: ["connections"] });
    } catch {
      setSyncNowError("Sync request failed. Please try again.");
    } finally {
      setSyncingNow(false);
    }
  };

  const handleRemove = () => {
    setRemoveError(null);
    remove.mutate(connectionId, {
      onSuccess: () => {
        setRemoveOpen(false);
        void navigate({ to: "/connections" });
      },
      onError: () => {
        setRemoveError("Failed to remove provider. Please try again.");
      },
    });
  };

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Connection detail
        </h1>
        {connection ? (
          <>
            <ConnectionCard connection={connection} />

            {/* Config summary for file providers */}
            {isFileProvider && (
              <div className="rounded-xl border border-border bg-card p-4 text-sm space-y-2">
                <p className="font-medium text-foreground">Source configuration</p>
                <dl className="grid gap-1.5">
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Source</dt>
                    <dd className="text-foreground font-mono text-xs break-all">
                      {(connection.config?.url as string | undefined) ??
                        (connection.config?.path as string | undefined) ??
                        "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Auth mode</dt>
                    <dd className="text-foreground">
                      {(connection.config?.auth_mode as string | undefined) ?? "none"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Sync interval</dt>
                    <dd className="text-foreground">
                      {
                        SYNC_INTERVAL_OPTIONS.find(
                          (o) => o.value === connection.config?.sync_interval,
                        )?.label ??
                          (connection.config?.sync_interval as string | undefined) ??
                          "Every hour"
                      }
                    </dd>
                  </div>
                </dl>
              </div>
            )}

            {/* Sync result / load feedback */}
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">Latest sync result</p>
              <SyncRunFeedback connectionId={connectionId} pollResetKey={syncPollKey} />
            </div>

            {syncNowError && (
              <p className="text-sm text-destructive">{syncNowError}</p>
            )}

            <div className="flex flex-wrap items-center gap-3">
              {/* Sync now */}
              <Button
                variant="outline"
                type="button"
                onClick={() => void handleSyncNow()}
                disabled={syncingNow}
              >
                {syncingNow ? "Syncing…" : "Sync now"}
              </Button>

              {/* Edit */}
              <Button variant="outline" type="button" onClick={openEdit}>
                Edit
              </Button>

              {/* Remove */}
              <Dialog open={removeOpen} onOpenChange={setRemoveOpen}>
                <DialogTrigger asChild>
                  <Button variant="destructive" type="button">
                    Remove provider
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Remove provider</DialogTitle>
                    <DialogDescription>
                      Permanently remove{" "}
                      <span className="font-medium text-foreground">
                        {connection.display_name || connection.provider_type}
                      </span>
                      ? This deletes the provider connection and all its
                      accounts, transactions, cards, and alarms. This cannot be
                      undone.
                    </DialogDescription>
                  </DialogHeader>
                  {removeError ? (
                    <p className="text-sm text-destructive">{removeError}</p>
                  ) : null}
                  <DialogFooter>
                    <Button
                      variant="outline"
                      type="button"
                      onClick={() => {
                        setRemoveOpen(false);
                        setRemoveError(null);
                      }}
                      disabled={remove.isPending}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="destructive"
                      type="button"
                      onClick={handleRemove}
                      disabled={remove.isPending}
                    >
                      {remove.isPending ? "Removing…" : "Remove permanently"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>

            {/* Edit dialog */}
            <Dialog open={editOpen} onOpenChange={setEditOpen}>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Edit connection</DialogTitle>
                  <DialogDescription>
                    Update the connection name
                    {isFileProvider ? ", source, auth mode, and sync frequency" : ""}.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="edit-name">Display name</Label>
                    <Input
                      id="edit-name"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      placeholder="My JSON feed"
                    />
                  </div>

                  {isFileProvider && (
                    <>
                      <div className="space-y-1.5">
                        <Label htmlFor="edit-source">File path or URL</Label>
                        <Input
                          id="edit-source"
                          value={editSource}
                          onChange={(e) => setEditSource(e.target.value)}
                          placeholder="/data/finances.json or https://..."
                        />
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="edit-auth-mode">Auth mode</Label>
                        <Select
                          value={editAuthMode}
                          onValueChange={setEditAuthMode}
                        >
                          <SelectTrigger id="edit-auth-mode" className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {AUTH_MODE_OPTIONS.map((o) => (
                              <SelectItem key={o.value} value={o.value}>
                                {o.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="edit-sync-interval">Sync frequency</Label>
                        <Select
                          value={editSyncInterval}
                          onValueChange={setEditSyncInterval}
                        >
                          <SelectTrigger id="edit-sync-interval" className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {SYNC_INTERVAL_OPTIONS.map((o) => (
                              <SelectItem key={o.value} value={o.value}>
                                {o.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </>
                  )}

                  {editError && (
                    <p className="text-sm text-destructive">{editError}</p>
                  )}
                </div>

                <DialogFooter>
                  <Button
                    variant="outline"
                    type="button"
                    onClick={() => setEditOpen(false)}
                    disabled={update.isPending}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="button"
                    onClick={handleEdit}
                    disabled={update.isPending}
                  >
                    {update.isPending ? "Saving…" : "Save"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        ) : (
          <p className="text-muted-foreground">Connection not found.</p>
        )}
      </div>
    </AppShell>
  );
}
