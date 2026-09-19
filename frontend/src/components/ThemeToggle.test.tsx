import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import ThemeToggle from "./ThemeToggle";
import { ThemeProvider } from "../contexts/ThemeContext";
import { THEME_STORAGE_KEY } from "../contexts/themeStorage";

function renderToggle() {
  return render(
    <ThemeProvider>
      <ThemeToggle />
    </ThemeProvider>,
  );
}

describe("ThemeToggle", () => {
  it("starts on the light palette when the OS prefers light", () => {
    renderToggle();
    expect(document.documentElement.getAttribute("data-theme")).toBe("system");
    expect(screen.getByRole("button", { name: /giao diện tối/i })).toBeInTheDocument();
  });

  it("switches to dark and persists the choice", async () => {
    const user = userEvent.setup();
    renderToggle();

    await user.click(screen.getByRole("button", { name: /giao diện tối/i }));

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(screen.getByRole("button", { name: /giao diện sáng/i })).toBeInTheDocument();
  });

  it("switches back to light on a second press", async () => {
    const user = userEvent.setup();
    renderToggle();

    await user.click(screen.getByRole("button", { name: /giao diện tối/i }));
    await user.click(screen.getByRole("button", { name: /giao diện sáng/i }));

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("honours a stored preference on mount", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "dark");
    renderToggle();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});
