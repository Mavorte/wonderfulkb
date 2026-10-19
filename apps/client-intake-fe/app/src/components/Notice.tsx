import KbIcon from "./KbIcon";

type Variant = "success" | "warning" | "error";

const ICONS = { success: "check", warning: "info", error: "info" } as const;

export default function Notice({
  variant,
  title,
  description,
}: {
  variant: Variant;
  title: string;
  description?: string;
}) {
  return (
    <div className={`app-notice app-notice--${variant}`} role={variant === "error" ? "alert" : "status"}>
      <KbIcon name={ICONS[variant]} />
      <div>
        <p className="app-notice__title">{title}</p>
        {description && <p>{description}</p>}
      </div>
    </div>
  );
}
