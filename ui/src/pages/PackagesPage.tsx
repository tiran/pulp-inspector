import {
  Alert,
  Breadcrumb,
  BreadcrumbItem,
  List,
  ListItem,
  SearchInput,
  Spinner,
  Title,
} from "@patternfly/react-core";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

interface PackageSummary {
  name: string;
}

interface PackageListResponse {
  base_path: string;
  packages: PackageSummary[];
  count: number;
}

function PackagesPage() {
  const {
    name = "",
    version = "",
    variant = "",
  } = useParams<{ name: string; version: string; variant: string }>();
  const indexPrefix = `/indexes/${name}/${version}/${variant}`;
  const [data, setData] = useState<PackageListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!name) return;
    setLoading(true);
    fetch(`/api${indexPrefix}/packages`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<PackageListResponse>;
      })
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [name, indexPrefix]);

  const filtered = useMemo(() => {
    if (!data) return [];
    if (!filter) return data.packages;
    const lower = filter.toLowerCase();
    return data.packages.filter((p) => p.name.toLowerCase().includes(lower));
  }, [data, filter]);

  if (loading) return <Spinner aria-label="Loading packages" />;
  if (error)
    return (
      <Alert variant="danger" title="Error loading packages">
        {error}
      </Alert>
    );
  if (!data) return null;

  return (
    <>
      <Breadcrumb style={{ marginBottom: "1rem" }}>
        <BreadcrumbItem>
          <Link to="/">Indexes</Link>
        </BreadcrumbItem>
        <BreadcrumbItem isActive>
          {name}-{version}-{variant}
        </BreadcrumbItem>
      </Breadcrumb>

      <Title headingLevel="h1" style={{ marginBottom: "0.5rem" }}>
        Packages in {name}-{version}-{variant}
      </Title>
      <p style={{ marginBottom: "1rem" }}>
        {data.count} packages total
        {filter && `, ${filtered.length} matching`}
      </p>
      <SearchInput
        placeholder="Filter packages..."
        value={filter}
        onChange={(_event, value) => setFilter(value)}
        onClear={() => setFilter("")}
        style={{ marginBottom: "1rem", maxWidth: "400px" }}
      />
      <List isPlain>
        {filtered.map((pkg) => (
          <ListItem key={pkg.name}>
            <Link to={`${indexPrefix}/packages/${pkg.name}`}>{pkg.name}</Link>
          </ListItem>
        ))}
      </List>
    </>
  );
}

export default PackagesPage;
