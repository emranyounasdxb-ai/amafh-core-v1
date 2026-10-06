import type { ReactNode } from "react";
import { DsIcon } from "../icons";
import { Button, type ButtonSize, type ButtonVariant } from "./Button";
import { IconButton } from "./IconButton";
import { Menu, type MenuItem } from "./Menu";

export function SplitButton({
  label,
  onClick,
  items,
  variant = "primary",
  size = "standard",
  disabled,
  menuLabel = "More actions",
}: {
  label: ReactNode;
  onClick: () => void;
  items: MenuItem[];
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  menuLabel?: string;
}) {
  return (
    <div className="ds-split">
      <Button
        variant={variant}
        size={size}
        disabled={disabled}
        onClick={onClick}
      >
        {label}
      </Button>
      <Menu
        label={menuLabel}
        items={items}
        trigger={
          <IconButton
            label={menuLabel}
            variant={variant === "primary" ? "primary" : "secondary"}
            size={size === "large" ? "large" : size}
            disabled={disabled}
            tooltip={false}
          >
            <DsIcon name="expand" size={size === "compact" ? 16 : 18} />
          </IconButton>
        }
      />
    </div>
  );
}

export function OverflowMenu({
  items,
  label = "More actions",
}: {
  items: MenuItem[];
  label?: string;
}) {
  return (
    <Menu
      label={label}
      align="bottom-end"
      items={items}
      trigger={
        <IconButton label={label} variant="ghost" size="compact">
          <DsIcon name="more" size={16} />
        </IconButton>
      }
    />
  );
}
