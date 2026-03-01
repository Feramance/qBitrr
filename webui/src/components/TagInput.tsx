import { useState, type KeyboardEvent } from "react";
import CloseIcon from "../icons/close.svg";

interface TagInputProps {
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function TagInput({ value, onChange, placeholder, disabled }: TagInputProps) {
  const [inputValue, setInputValue] = useState("");

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const trimmed = inputValue.trim();
      if (trimmed && !value.includes(trimmed)) {
        onChange([...value, trimmed]);
        setInputValue("");
      }
    } else if (e.key === "Backspace" && !inputValue && value.length > 0) {
      // Remove last tag on backspace if input is empty
      onChange(value.slice(0, -1));
    }
  };

  const handleRemove = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  return (
    <div className="tag-input-container">
      <div className="tag-input-wrapper">
        {value.map((tag, index) => (
          <span key={tag} className="tag">
            {tag}
            {!disabled && (
              <button
                type="button"
                className="tag-remove"
                onClick={() => handleRemove(index)}
                aria-label={`Remove ${tag}`}
              >
                <img src={CloseIcon} alt="Remove" />
              </button>
            )}
          </span>
        ))}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={value.length === 0 ? placeholder : ""}
          disabled={disabled}
          className="tag-input"
        />
      </div>
      <div className="tag-input-hint">
        Press Enter or comma to add a category
      </div>
    </div>
  );
}
