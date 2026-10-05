import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Venture Forge · From possibility to proof",
  description: "A considered workspace for founder hypotheses, evidence and decisions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Browser extensions can inject crxlauncher attributes before React hydrates.
  // Limit suppression to the root element so descendant mismatches remain visible.
  return <html lang="en" suppressHydrationWarning><body>{children}</body></html>;
}
