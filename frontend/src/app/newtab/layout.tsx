import type { Metadata } from "next";

export const metadata: Metadata = { title: "New tab" };

export default function NewTabLayout({ children }: { children: React.ReactNode }) {
  return children;
}
