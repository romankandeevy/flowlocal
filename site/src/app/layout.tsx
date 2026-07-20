import type { Metadata } from "next";
import { Onest, JetBrains_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import { ScrollProgress } from "@/components/scroll-progress";
import { Navbar } from "@/components/navbar";
import "./globals.css";

const onest = Onest({
  subsets: ["cyrillic", "latin"],
  variable: "--font-onest",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["cyrillic", "latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FlowLocal — диктовка, которая работает без интернета",
  description:
    "Зажал клавишу, сказал, отпустил — текст в активном окне. Русская речь распознаётся вдвое точнее Whisper, на процессоре, без облака и без подписки.",
  metadataBase: new URL("https://romankandeevy.github.io"),
  alternates: { canonical: "/flowlocal/" },
  openGraph: {
    title: "FlowLocal — диктовка, которая работает без интернета",
    description:
      "Голос не покидает компьютер. Не потому что мы обещаем, а потому что некуда.",
    url: "https://romankandeevy.github.io/flowlocal/",
    siteName: "FlowLocal",
    locale: "ru_RU",
    type: "website",
    images: [
      {
        url: "/flowlocal/og-image.webp",
        width: 1200,
        height: 630,
        alt: "FlowLocal — диктовка без интернета",
      },
    ],
  },
  icons: {
    icon: [
      { url: "/flowlocal/favicon-16.svg", sizes: "16x16", type: "image/svg+xml" },
      { url: "/flowlocal/favicon-32.svg", sizes: "32x32", type: "image/svg+xml" },
    ],
    apple: { url: "/flowlocal/apple-touch-icon.png", sizes: "180x180" },
  },
};

export const viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "FlowLocal",
  applicationCategory: "Multimedia",
  operatingSystem: "Windows 10/11",
  description:
    "Локальная диктовка для Windows на модели GigaAM RNN-T. Работает на процессоре, без интернета.",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "USD",
  },
  license: "https://github.com/romankandeevy/flowlocal/blob/main/LICENSE",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="ru"
      className={`${onest.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="min-h-screen bg-paper text-ink antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <ScrollProgress />
          <Navbar />
          <main>{children}</main>
          <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-border py-10 text-xs text-secondary">
            <span>FlowLocal — свободная программа под лицензией MIT</span>
            <span>
              <a
                href="https://github.com/romankandeevy/flowlocal"
                className="transition-colors hover:text-ink"
              >
                GitHub
              </a>
              <span className="mx-1.5">·</span>
              <a
                href="https://github.com/romankandeevy/flowlocal/releases"
                className="transition-colors hover:text-ink"
              >
                Все версии
              </a>
            </span>
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
