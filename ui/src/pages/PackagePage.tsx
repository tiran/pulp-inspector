import {
  Alert,
  Breadcrumb,
  BreadcrumbItem,
  Label,
  List,
  ListItem,
  Spinner,
  Title,
} from "@patternfly/react-core";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

interface WheelFile {
  filename: string;
  url: string;
  requires_python: string | null;
  digests: Record<string, string>;
}

interface PackageVersion {
  version: string;
  wheels: WheelFile[];
}

interface PackageDetailResponse {
  base_path: string;
  package_name: string;
  versions: PackageVersion[];
}

function PackagePage() {
  const {
    name = "",
    version = "",
    variant = "",
    packageName = "",
  } = useParams<{
    name: string;
    version: string;
    variant: string;
    packageName: string;
  }>();
  const indexPrefix = `/indexes/${name}/${version}/${variant}`;
  const [data, setData] = useState<PackageDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!name || !packageName) return;
    setLoading(true);
    fetch(`/api${indexPrefix}/packages/${packageName}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<PackageDetailResponse>;
      })
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [name, indexPrefix, packageName]);

  if (loading) return <Spinner aria-label="Loading package" />;
  if (error)
    return (
      <Alert variant="danger" title="Error loading package">
        {error}
      </Alert>
    );
  if (!data) return null;

  const allWheels = data.versions.flatMap((ver) =>
    ver.wheels.map((whl) => ({ ...whl, version: ver.version })),
  );

  return (
    <>
      <Breadcrumb style={{ marginBottom: "1rem" }}>
        <BreadcrumbItem>
          <Link to="/">Indexes</Link>
        </BreadcrumbItem>
        <BreadcrumbItem>
          <Link to={`${indexPrefix}/packages`}>
            {name}-{version}-{variant}
          </Link>
        </BreadcrumbItem>
        <BreadcrumbItem isActive>{packageName}</BreadcrumbItem>
      </Breadcrumb>

      <Title headingLevel="h1" style={{ marginBottom: "1rem" }}>
        {packageName}
      </Title>

      <List isPlain>
        {allWheels.map((whl) => (
          <ListItem key={whl.filename}>
            <Link to={`${indexPrefix}/packages/${packageName}/${whl.filename}`}>
              {whl.filename}
            </Link>
            {whl.requires_python && (
              <Label color="blue" style={{ marginLeft: "0.5rem" }}>
                Python {whl.requires_python}
              </Label>
            )}
          </ListItem>
        ))}
      </List>
    </>
  );
}

export default PackagePage;
