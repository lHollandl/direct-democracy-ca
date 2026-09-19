import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "A ballot cycle",
};

export default function Page() {
  return <PageClient />;
}
