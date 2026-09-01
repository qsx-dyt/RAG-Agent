// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import UploadDropzone from "./UploadDropzone";

it("calls onUpload with files", async () => {
  const onUpload = vi.fn();
  const { container } = render(<UploadDropzone onUpload={onUpload} />);
  const input = container.querySelector("input[type=file]")!;
  const file = new File(["x"], "a.md", { type: "text/markdown" });
  fireEvent.change(input, { target: { files: [file] } });
  await waitFor(() => expect(onUpload).toHaveBeenCalledWith([file]));
});
