import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Roll control — CFD sweep analysis',
  description: 'Fine-mesh OpenFOAM and SimScale deflection sweeps, linear fits, and solver comparisons.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
