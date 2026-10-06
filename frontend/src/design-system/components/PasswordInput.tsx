import { useState, type InputHTMLAttributes } from "react";
import { DsIcon } from "../icons";
import { IconButton } from "./IconButton";
import { TextInput } from "./TextInput";

export function PasswordInput({
  ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  compact?: boolean;
  invalid?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <TextInput
      {...props}
      type={visible ? "text" : "password"}
      autoComplete={props.autoComplete ?? "current-password"}
      suffix={
        <IconButton
          label={visible ? "Hide password" : "Show password"}
          variant="ghost"
          size="compact"
          onClick={() => setVisible((current) => !current)}
        >
          {visible ? <DsIcon name="hide" size={16} /> : <DsIcon name="view" size={16} />}
        </IconButton>
      }
    />
  );
}
