import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "The ballot",
};

export default function Page() {
  return <PageClient />;
}
