import type { Metadata } from "next";
import { Geist, Geist_Mono, Quicksand } from "next/font/google";
import "./globals.css";
import { UserProvider } from "../lib/userContext";
import RootShell from "../components/RootShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const quicksand = Quicksand({
  variable: "--font-quicksand",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Medly - Hospital Management",
  description: "Quản lí thông tin lịch khám của các bệnh viện liên kết với Medly",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
  <body className={`${geistSans.variable} ${geistMono.variable} ${quicksand.variable} antialiased bg-white text-black`}>
  <UserProvider>
        <RootShell>{children}</RootShell>
  </UserProvider>
      </body>
    </html>
  );
}
