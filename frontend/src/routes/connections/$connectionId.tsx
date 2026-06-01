import {
  createRoute,
  redirect,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import type { AuthContextValue } from "@/features/auth/AuthProvider";
import { ConnectionCard } from "@/features/connections/ConnectionCard";
import {
  useConnections,
  useRemoveConnection,
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
import { rootRoute } from "../__root";

export const connectionDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/connections/$connectionId",
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: "/login" });
  },
  component: ConnectionDetailPage,
});

function ConnectionDetailPage() {
  const { connectionId } = useParams({ from: "/connections/$connectionId" });
  const { data = [] } = useConnections();
  const connection = data.find((item) => item.id === connectionId);
  const navigate = useNavigate();
  const remove = useRemoveConnection();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRemove = () => {
    setError(null);
    remove.mutate(connectionId, {
      onSuccess: () => {
        setOpen(false);
        void navigate({ to: "/connections" });
      },
      onError: () => {
        setError("Failed to remove provider. Please try again.");
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
            <div className="flex items-center gap-4">
              <Dialog open={open} onOpenChange={setOpen}>
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
                  {error ? (
                    <p className="text-sm text-destructive">{error}</p>
                  ) : null}
                  <DialogFooter>
                    <Button
                      variant="outline"
                      type="button"
                      onClick={() => {
                        setOpen(false);
                        setError(null);
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
          </>
        ) : (
          <p className="text-muted-foreground">Connection not found.</p>
        )}
      </div>
    </AppShell>
  );
}
