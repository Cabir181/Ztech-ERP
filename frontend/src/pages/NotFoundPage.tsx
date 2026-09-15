import { Link } from "react-router-dom";
import { EmptyState, PageHeader } from "../components/primitives";

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState
        title="There is nothing at this address"
        description="The link may be out of date, or the record may have been removed."
        action={<Link to="/">Back to the overview</Link>}
      />
    </>
  );
}
