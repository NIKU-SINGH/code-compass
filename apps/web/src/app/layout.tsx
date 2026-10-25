import type { Metadata } from "next";
import { JetBrains_Mono, Lato, Lora, Poppins } from "next/font/google";
import type { ReactNode } from "react";
import { THEME_INIT_SCRIPT } from "@/components/shell/theme";
import "@/styles/globals.css";

const lato = Lato({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-lato", display: "swap" });
const lora = Lora({ subsets: ["latin"], variable: "--font-lora", display: "swap" });
const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-poppins",
  display: "swap",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Code Compass",
  description: "Visualize your codebase as a knowledge graph",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // data-theme is set before paint by the inline script, so the server markup can't know it.
    <html lang="en" className={`${lato.variable} ${lora.variable} ${poppins.variable} ${jetbrainsMono.variable} h-full`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="font-sans h-svh overflow-hidden flex flex-col">{children}</body>
    </html>
  );
}
