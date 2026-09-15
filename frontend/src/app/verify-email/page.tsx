import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Confirming your email address",
};

export default function Page() {
  return <PageClient />;
}
