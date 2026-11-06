import "./globals.css";
import React from "react";

export const metadata = {
  title: "Manager Portal — Cinema & Show Operations",
  description: "Manager dashboard for creating events and listing shows on the Show Ticket Booking System.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#070a12] text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
