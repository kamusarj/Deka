import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { CSSProperties, KeyboardEvent } from "react";
import { createPortal } from "react-dom";

export type SelectValue = string | number;

export interface SelectOption<T extends SelectValue = SelectValue> {
  value: T;
  label: string;
  disabled?: boolean;
}

interface SelectControlProps<T extends SelectValue> {
  value: T;
  options: SelectOption<T>[];
  onChange: (value: T) => void;
  ariaLabel: string;
  disabled?: boolean;
  className?: string;
}

interface MenuPosition {
  left: number;
  maxHeight: number;
  placement: "top" | "bottom";
  top: number;
  width: number;
}

const VIEWPORT_MARGIN = 12;
const MENU_GAP = 7;
const MAX_MENU_HEIGHT = 304;

function sameValue(left: SelectValue, right: SelectValue) {
  return String(left) === String(right);
}

export default function SelectControl<T extends SelectValue>({
  value,
  options,
  onChange,
  ariaLabel,
  disabled = false,
  className = "",
}: SelectControlProps<T>) {
  const reactId = useId().replace(/:/g, "");
  const listboxId = `select-listbox-${reactId}`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const typeaheadRef = useRef("");
  const typeaheadTimerRef = useRef<number | null>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [position, setPosition] = useState<MenuPosition | null>(null);
  const menuOpen = open && !disabled;

  const selectedIndex = useMemo(
    () => options.findIndex((option) => sameValue(option.value, value)),
    [options, value],
  );
  const selectedOption = options[selectedIndex];

  const enabledIndexes = useMemo(
    () => options.flatMap((option, index) => (option.disabled ? [] : [index])),
    [options],
  );

  const findEnabledIndex = useCallback(
    (start: number, direction: 1 | -1) => {
      if (enabledIndexes.length === 0) return -1;
      const current = enabledIndexes.indexOf(start);
      if (current === -1) {
        return direction === 1 ? enabledIndexes[0] : enabledIndexes[enabledIndexes.length - 1];
      }
      return enabledIndexes[(current + direction + enabledIndexes.length) % enabledIndexes.length];
    },
    [enabledIndexes],
  );

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;

    const rect = trigger.getBoundingClientRect();
    const desiredHeight = Math.min(MAX_MENU_HEIGHT, options.length * 46 + 12);
    const spaceBelow = window.innerHeight - rect.bottom - MENU_GAP - VIEWPORT_MARGIN;
    const spaceAbove = rect.top - MENU_GAP - VIEWPORT_MARGIN;
    const placement = spaceBelow < Math.min(180, desiredHeight) && spaceAbove > spaceBelow
      ? "top"
      : "bottom";
    const available = placement === "top" ? spaceAbove : spaceBelow;
    const maxHeight = Math.max(92, Math.min(MAX_MENU_HEIGHT, available));
    const width = Math.min(
      Math.max(rect.width, 220),
      window.innerWidth - VIEWPORT_MARGIN * 2,
    );
    const left = Math.min(
      Math.max(VIEWPORT_MARGIN, rect.left),
      window.innerWidth - VIEWPORT_MARGIN - width,
    );
    const renderedHeight = Math.min(desiredHeight, maxHeight);
    const top = placement === "top"
      ? Math.max(VIEWPORT_MARGIN, rect.top - MENU_GAP - renderedHeight)
      : rect.bottom + MENU_GAP;

    setPosition({ left, maxHeight, placement, top, width });
  }, [options.length]);

  const openMenu = useCallback(() => {
    if (disabled || triggerRef.current?.matches(":disabled") || enabledIndexes.length === 0) return;
    const initial = selectedIndex >= 0 && !options[selectedIndex]?.disabled
      ? selectedIndex
      : enabledIndexes[0];
    setActiveIndex(initial);
    setOpen(true);
  }, [disabled, enabledIndexes, options, selectedIndex]);

  const closeMenu = useCallback((restoreFocus = false) => {
    setOpen(false);
    setPosition(null);
    if (restoreFocus) requestAnimationFrame(() => triggerRef.current?.focus());
  }, []);

  const choose = useCallback((index: number) => {
    // Options live outside their fieldset in a portal, so check the trigger's
    // native disabled state before allowing a selection.
    if (disabled || triggerRef.current?.matches(":disabled")) {
      closeMenu();
      return;
    }
    const option = options[index];
    if (!option || option.disabled) return;
    if (!sameValue(option.value, value)) onChange(option.value);
    closeMenu(true);
  }, [closeMenu, disabled, onChange, options, value]);

  useEffect(() => {
    if (disabled) closeMenu();
  }, [closeMenu, disabled]);

  useLayoutEffect(() => {
    if (!menuOpen) return;
    updatePosition();
  }, [menuOpen, updatePosition]);

  useEffect(() => {
    if (!menuOpen) return;

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      closeMenu();
    };
    const onViewportChange = () => updatePosition();

    document.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("resize", onViewportChange);
    window.addEventListener("scroll", onViewportChange, true);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("resize", onViewportChange);
      window.removeEventListener("scroll", onViewportChange, true);
    };
  }, [closeMenu, menuOpen, updatePosition]);

  useEffect(() => () => {
    if (typeaheadTimerRef.current !== null) window.clearTimeout(typeaheadTimerRef.current);
  }, []);

  function handleTypeahead(key: string) {
    typeaheadRef.current += key.toLocaleLowerCase("vi");
    if (typeaheadTimerRef.current !== null) window.clearTimeout(typeaheadTimerRef.current);
    typeaheadTimerRef.current = window.setTimeout(() => {
      typeaheadRef.current = "";
      typeaheadTimerRef.current = null;
    }, 650);

    const query = typeaheadRef.current;
    const ordered = [...enabledIndexes.filter((index) => index > activeIndex), ...enabledIndexes];
    const match = ordered.find((index) => options[index].label.toLocaleLowerCase("vi").startsWith(query));
    if (match !== undefined) {
      setActiveIndex(match);
      document.getElementById(`${listboxId}-option-${match}`)?.scrollIntoView?.({ block: "nearest" });
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (disabled || triggerRef.current?.matches(":disabled")) return;

    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        openMenu();
      } else {
        setActiveIndex((current) => findEnabledIndex(current, event.key === "ArrowDown" ? 1 : -1));
      }
      return;
    }
    if (event.key === "Home" && open) {
      event.preventDefault();
      setActiveIndex(enabledIndexes[0] ?? -1);
      return;
    }
    if (event.key === "End" && open) {
      event.preventDefault();
      setActiveIndex(enabledIndexes[enabledIndexes.length - 1] ?? -1);
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (open) choose(activeIndex);
      else openMenu();
      return;
    }
    if (event.key === "Escape" && open) {
      event.preventDefault();
      closeMenu(true);
      return;
    }
    if (event.key === "Tab" && open) {
      closeMenu();
      return;
    }
    if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      if (!open) openMenu();
      handleTypeahead(event.key);
    }
  }

  const activeOptionId = menuOpen && activeIndex >= 0
    ? `${listboxId}-option-${activeIndex}`
    : undefined;
  const wrapperClass = `select-control ${menuOpen ? "select-control-open" : ""} ${className}`.trim();
  const menuStyle = position
    ? ({
        "--select-menu-max-height": `${position.maxHeight}px`,
        left: position.left,
        top: position.top,
        width: position.width,
      } as CSSProperties)
    : undefined;

  return (
    <span className={wrapperClass} data-disabled={disabled || undefined}>
      <button
        ref={triggerRef}
        type="button"
        className="select-control-trigger"
        role="combobox"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={menuOpen}
        aria-controls={listboxId}
        aria-activedescendant={activeOptionId}
        disabled={disabled}
        onClick={() => (open ? closeMenu() : openMenu())}
        onKeyDown={onKeyDown}
      >
        <span className={`select-control-value ${selectedOption ? "" : "select-control-placeholder"}`}>
          {selectedOption?.label ?? "Chọn một giá trị"}
        </span>
        <span className="select-control-divider" aria-hidden="true" />
        <svg className="select-control-chevron" viewBox="0 0 16 16" aria-hidden="true">
          <path d="m4 6 4 4 4-4" />
        </svg>
      </button>

      {menuOpen && position && createPortal(
        <div
          ref={menuRef}
          id={listboxId}
          role="listbox"
          aria-label={ariaLabel}
          className={`select-control-menu select-control-menu-${position.placement}`}
          style={menuStyle}
        >
          <div className="select-control-menu-scroll">
            {options.map((option, index) => {
              const selected = sameValue(option.value, value);
              const active = index === activeIndex;
              return (
                <div
                  id={`${listboxId}-option-${index}`}
                  key={`${String(option.value)}-${index}`}
                  role="option"
                  aria-selected={selected}
                  aria-disabled={option.disabled || undefined}
                  className={`select-control-option ${active ? "select-control-option-active" : ""} ${selected ? "select-control-option-selected" : ""}`}
                  onPointerEnter={() => !option.disabled && setActiveIndex(index)}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(index)}
                >
                  <span className="select-control-option-mark" aria-hidden="true">
                    {selected ? "✓" : ""}
                  </span>
                  <span className="select-control-option-label">{option.label}</span>
                </div>
              );
            })}
          </div>
        </div>,
        document.body,
      )}
    </span>
  );
}
