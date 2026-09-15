import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Sign in",
};

export default function Page() {
  return <PageClient />;
}
