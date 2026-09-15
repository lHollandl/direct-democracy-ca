import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Reset your password",
};

export default function Page() {
  return <PageClient />;
}
