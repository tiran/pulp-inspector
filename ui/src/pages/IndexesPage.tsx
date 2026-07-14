import {
  Alert,
  Card,
  CardBody,
  CardTitle,
  Label,
  LabelGroup,
  List,
  ListItem,
  Spinner,
  Title,
} from "@patternfly/react-core";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface IndexVariant {
  name: string;
  base_path: string;
  simple_url: string;
  labels: Record<string, string>;
  route_name: string;
  route_version: string;
  route_variant: string;
}

interface IndexVersionGroup {
  version: string;
  test: boolean;
  variants: IndexVariant[];
}

interface IndexListResponse {
  versions: IndexVersionGroup[];
}

function IndexesPage() {
  const [data, setData] = useState<IndexListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/indexes")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<IndexListResponse>;
      })
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner aria-label="Loading indexes" />;
  if (error)
    return (
      <Alert variant="danger" title="Error loading indexes">
        {error}
      </Alert>
    );
  if (!data) return null;

  return (
    <>
      <Title headingLevel="h1" style={{ marginBottom: "1rem" }}>
        Browse Indexes
      </Title>
      {data.versions.map((group) => (
        <Card
          key={`${group.version}-${group.test}`}
          style={{ marginBottom: "1rem" }}
        >
          <CardTitle>
            {group.version}
            {group.test && (
              <Label color="orange" style={{ marginLeft: "0.5rem" }}>
                test
              </Label>
            )}
          </CardTitle>
          <CardBody>
            <List isPlain>
              {group.variants.map((variant) => (
                <ListItem key={variant.base_path}>
                  <Link
                    to={`/indexes/${variant.route_name}/${variant.route_version}/${variant.route_variant}/packages`}
                  >
                    {variant.name}
                  </Link>
                  <LabelGroup
                    style={{ marginLeft: "0.5rem", display: "inline-flex" }}
                  >
                    {variant.labels.accelerator && (
                      <Label color="blue">{variant.labels.accelerator}</Label>
                    )}
                    {variant.labels.rhel_version && (
                      <Label color="grey">{variant.labels.rhel_version}</Label>
                    )}
                  </LabelGroup>
                </ListItem>
              ))}
            </List>
          </CardBody>
        </Card>
      ))}
    </>
  );
}

export default IndexesPage;
