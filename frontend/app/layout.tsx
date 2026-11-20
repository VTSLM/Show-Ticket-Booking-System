import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";
import { LocationProvider } from "@/contexts/LocationContext";
import LocationPicker from "@/components/LocationPicker";
import { Toaster } from "react-hot-toast";
import Navbar from "@/components/Navbar";
import ChatWidget from "@/components/ChatWidget";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TicketFlow — Show Booking",
  description: "Book tickets for movies, concerts and theatre shows",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthProvider>
          <LocationProvider>
            <Navbar />
            <main className="min-h-screen bg-transparent">{children}</main>
            <LocationPicker />
            <ChatWidget />
            <Toaster position="top-right" />
          </LocationProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
