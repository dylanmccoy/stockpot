import { useRef, useState, type ReactNode, type RefObject } from "react";
import {
  Badge,
  Button,
  Card,
  DataTable,
  Dialog,
  Field,
  Input,
  Select,
  Stepper,
  Textarea,
  ToastProvider,
  useToast,
} from "../../components";
import styles from "./ComponentsDemo.module.css";

/**
 * Dev-only visual harness: every primitive rendered in a forced-light and a
 * forced-dark pane so the a11y bar (docs/frontend/spec.md §9) can be eyeballed
 * in both themes. Wired into the router behind `import.meta.env.DEV` only.
 */
export default function ComponentsDemo() {
  return (
    <main className={styles.page}>
      <h1>Component demo</h1>
      <p>Every primitive, both themes. Not shipped in production.</p>
      <div className={styles.themes}>
        <Pane scope="light" />
        <Pane scope="dark" />
      </div>
    </main>
  );
}

/**
 * One forced-theme pane. Its own `ToastProvider` and an in-pane portal host keep
 * the toast region and the `Dialog` inside `data-theme`, so the overlay
 * primitives are actually previewed in the selected palette too.
 */
function Pane({ scope }: { scope: "light" | "dark" }) {
  const overlayHost = useRef<HTMLDivElement>(null);
  return (
    <section
      data-theme={scope}
      className={styles.pane}
      aria-label={scope === "light" ? "Light theme" : "Dark theme"}
    >
      <ToastProvider>
        <Gallery scope={scope} overlayHost={overlayHost} />
        <div ref={overlayHost} />
      </ToastProvider>
    </section>
  );
}

interface Row {
  id: number;
  item: string;
  qty: string;
}

const ROWS: Row[] = [
  { id: 1, item: "Flour", qty: "500 g" },
  { id: 2, item: "Eggs", qty: "6" },
];

function Gallery({
  scope,
  overlayHost,
}: {
  scope: "light" | "dark";
  overlayHost: RefObject<HTMLDivElement>;
}) {
  const toast = useToast();
  const [multiplier, setMultiplier] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <>
      <Block title="Buttons">
        <div className={styles.row}>
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button loading>Loading</Button>
        </div>
      </Block>

      <Block title="Fields">
        <Field label="Recipe name" hint="Shown in the list." required>
          <Input placeholder="e.g. Focaccia" defaultValue="" />
        </Field>
        <Field label="Notes">
          <Textarea rows={2} placeholder="Optional" />
        </Field>
        <Field label="Cuisine">
          <Select defaultValue="">
            <option value="">Any</option>
            <option value="italian">Italian</option>
            <option value="thai">Thai</option>
          </Select>
        </Field>
        <Field label="Servings" error="Must be a whole number greater than 0.">
          <Input inputMode="numeric" defaultValue="0" />
        </Field>
      </Block>

      <Block title="Card">
        <Card>
          <strong>Weeknight pasta</strong>
          <p>A padded surface for list items and panels.</p>
        </Card>
      </Block>

      <Block title="Badges">
        <div className={styles.row}>
          <Badge>Neutral</Badge>
          <Badge tone="ok" icon="✓">
            Available
          </Badge>
          <Badge tone="warn" icon="!">
            Check what you have
          </Badge>
          <Badge tone="danger" icon="×">
            Short
          </Badge>
          <Badge tone="accent">generated</Badge>
        </div>
      </Block>

      <Block title="Stepper">
        <Stepper
          label="Multiplier"
          value={multiplier}
          onChange={setMultiplier}
        />
      </Block>

      <Block title="DataTable">
        <DataTable
          caption="Inventory sample"
          columns={[
            { key: "item", header: "Item", render: (r) => r.item },
            {
              key: "qty",
              header: "Quantity",
              render: (r) => r.qty,
              align: "end",
            },
          ]}
          rows={ROWS}
          rowKey={(r) => r.id}
        />
      </Block>

      <Block title="Overlays">
        <div className={styles.row}>
          <Button variant="secondary" onClick={() => setDialogOpen(true)}>
            Open dialog
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              toast.show(`Saved from the ${scope} pane`, { variant: "success" })
            }
          >
            Success toast
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              toast.show("Something went wrong", { variant: "error" })
            }
          >
            Error toast
          </Button>
        </div>
        <Dialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          container={overlayHost.current}
          title="Delete recipe?"
          footer={
            <>
              <Button variant="ghost" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button variant="danger" onClick={() => setDialogOpen(false)}>
                Delete
              </Button>
            </>
          }
        >
          <p>This can’t be undone.</p>
        </Dialog>
      </Block>
    </>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>{title}</h2>
      {children}
    </section>
  );
}
