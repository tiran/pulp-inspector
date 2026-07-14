import {
  Alert,
  Breadcrumb,
  BreadcrumbItem,
  Card,
  CardBody,
  CardTitle,
  DescriptionList,
  DescriptionListDescription,
  DescriptionListGroup,
  DescriptionListTerm,
  Label,
  List,
  ListItem,
  Spinner,
  Title,
} from "@patternfly/react-core";
import hljs from "highlight.js/lib/core";
import cpp from "highlight.js/lib/languages/cpp";
import css from "highlight.js/lib/languages/css";
import diff from "highlight.js/lib/languages/diff";
import ini from "highlight.js/lib/languages/ini";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import python from "highlight.js/lib/languages/python";
import rust from "highlight.js/lib/languages/rust";
import shell from "highlight.js/lib/languages/shell";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";
import "highlight.js/styles/github.min.css";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

hljs.registerLanguage("python", python);
hljs.registerLanguage("json", json);
hljs.registerLanguage("yaml", yaml);
hljs.registerLanguage("markdown", markdown);
hljs.registerLanguage("xml", xml);
hljs.registerLanguage("css", css);
hljs.registerLanguage("ini", ini);
hljs.registerLanguage("shell", shell);
hljs.registerLanguage("diff", diff);
hljs.registerLanguage("rust", rust);
hljs.registerLanguage("cpp", cpp);

const EXT_TO_LANG: Record<string, string> = {
  ".py": "python",
  ".pyi": "python",
  ".json": "json",
  ".yaml": "yaml",
  ".yml": "yaml",
  ".md": "markdown",
  ".rst": "markdown",
  ".xml": "xml",
  ".html": "xml",
  ".htm": "xml",
  ".css": "css",
  ".cfg": "ini",
  ".ini": "ini",
  ".toml": "ini",
  ".sh": "shell",
  ".bash": "shell",
  ".diff": "diff",
  ".patch": "diff",
  ".rs": "rust",
  ".c": "cpp",
  ".h": "cpp",
  ".cpp": "cpp",
  ".cxx": "cpp",
  ".hpp": "cpp",
};

function detectLanguage(filepath: string): string | undefined {
  const name = filepath.split("/").pop() || "";
  if (name === "PKG-INFO" || name === "METADATA") return "yaml";
  if (name === "RECORD") return undefined;
  const dotIdx = name.lastIndexOf(".");
  if (dotIdx >= 0) {
    return EXT_TO_LANG[name.slice(dotIdx).toLowerCase()];
  }
  return undefined;
}

interface SOInfo {
  soname: string;
  version: string;
}

interface ELFInfoResponse {
  filepath: string;
  size: number;
  machine: string | null;
  is_dso: boolean;
  is_exec: boolean;
  soname: string | null;
  interp: string | null;
  runpath: string[];
  requires: SOInfo[];
  provides: SOInfo[];
}

interface WheelFileContentResponse {
  filepath: string;
  content: string;
  size: number;
  is_binary: boolean;
  truncated: boolean;
}

type FileResponse = WheelFileContentResponse | ELFInfoResponse;

function isELF(data: FileResponse): data is ELFInfoResponse {
  return "machine" in data;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ELFView({ data }: { data: ELFInfoResponse }) {
  return (
    <>
      <Card style={{ marginBottom: "1rem" }}>
        <CardTitle>ELF Info</CardTitle>
        <CardBody>
          <DescriptionList isHorizontal>
            {data.machine && (
              <DescriptionListGroup>
                <DescriptionListTerm>Machine</DescriptionListTerm>
                <DescriptionListDescription>
                  {data.machine}
                </DescriptionListDescription>
              </DescriptionListGroup>
            )}
            <DescriptionListGroup>
              <DescriptionListTerm>Type</DescriptionListTerm>
              <DescriptionListDescription>
                {data.is_dso && <Label color="blue">DSO</Label>}
                {data.is_exec && (
                  <Label color="green" style={{ marginLeft: "0.25rem" }}>
                    Executable
                  </Label>
                )}
                {!data.is_dso && !data.is_exec && "Unknown"}
              </DescriptionListDescription>
            </DescriptionListGroup>
            {data.soname && (
              <DescriptionListGroup>
                <DescriptionListTerm>SONAME</DescriptionListTerm>
                <DescriptionListDescription>
                  <code>{data.soname}</code>
                </DescriptionListDescription>
              </DescriptionListGroup>
            )}
            {data.interp && (
              <DescriptionListGroup>
                <DescriptionListTerm>Interpreter</DescriptionListTerm>
                <DescriptionListDescription>
                  <code>{data.interp}</code>
                </DescriptionListDescription>
              </DescriptionListGroup>
            )}
            {data.runpath.length > 0 && (
              <DescriptionListGroup>
                <DescriptionListTerm>RUNPATH</DescriptionListTerm>
                <DescriptionListDescription>
                  <code>{data.runpath.join(":")}</code>
                </DescriptionListDescription>
              </DescriptionListGroup>
            )}
          </DescriptionList>
        </CardBody>
      </Card>

      {data.provides.length > 0 && (
        <Card style={{ marginBottom: "1rem" }}>
          <CardTitle>Provides ({data.provides.length})</CardTitle>
          <CardBody>
            <List isPlain>
              {data.provides.map((s) => (
                <ListItem key={`${s.soname}-${s.version}`}>
                  <code>{s.soname}</code>
                  {s.version && (
                    <Label color="blue" style={{ marginLeft: "0.5rem" }}>
                      {s.version}
                    </Label>
                  )}
                </ListItem>
              ))}
            </List>
          </CardBody>
        </Card>
      )}

      {data.requires.length > 0 && (
        <Card style={{ marginBottom: "1rem" }}>
          <CardTitle>Requires ({data.requires.length})</CardTitle>
          <CardBody>
            <List isPlain>
              {data.requires.map((s) => (
                <ListItem key={`${s.soname}-${s.version}`}>
                  <code>{s.soname}</code>
                  {s.version && (
                    <Label color="orange" style={{ marginLeft: "0.5rem" }}>
                      {s.version}
                    </Label>
                  )}
                </ListItem>
              ))}
            </List>
          </CardBody>
        </Card>
      )}
    </>
  );
}

function WheelFilePage() {
  const {
    name = "",
    version = "",
    variant = "",
    packageName = "",
    filename = "",
  } = useParams<{
    name: string;
    version: string;
    variant: string;
    packageName: string;
    filename: string;
  }>();
  const location = useLocation();
  const indexPrefix = `/indexes/${name}/${version}/${variant}`;
  const wheelPath = `${indexPrefix}/packages/${packageName}/${filename}`;

  const filesMarker = `${wheelPath}/files/`;
  const filepath = location.pathname.startsWith(filesMarker)
    ? location.pathname.slice(filesMarker.length)
    : "";

  const [data, setData] = useState<FileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!name || !filename || !filepath) return;
    setLoading(true);
    fetch(`/api${wheelPath}/files/${filepath}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<FileResponse>;
      })
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [name, wheelPath, filename, filepath]);

  const highlighted = useMemo(() => {
    if (!data || isELF(data) || data.is_binary) return null;
    const lang = detectLanguage(data.filepath);
    if (lang) {
      try {
        return hljs.highlight(data.content, { language: lang }).value;
      } catch {
        // fall through
      }
    }
    return null;
  }, [data]);

  if (loading) return <Spinner aria-label="Loading file" />;
  if (error)
    return (
      <Alert variant="danger" title="Error loading file">
        {error}
      </Alert>
    );
  if (!data) return null;

  const shortName = filepath.split("/").pop() || filepath;

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
        <BreadcrumbItem>
          <Link to={`${indexPrefix}/packages/${packageName}`}>
            {packageName}
          </Link>
        </BreadcrumbItem>
        <BreadcrumbItem>
          <Link to={wheelPath}>{filename}</Link>
        </BreadcrumbItem>
        <BreadcrumbItem isActive>{shortName}</BreadcrumbItem>
      </Breadcrumb>

      <Title headingLevel="h1" style={{ marginBottom: "0.5rem" }}>
        {filepath}
      </Title>
      <p
        style={{
          marginBottom: "1rem",
          color: "var(--pf-t--color--gray--60)",
        }}
      >
        {formatSize(data.size)}
      </p>

      {isELF(data) ? (
        <ELFView data={data} />
      ) : data.truncated ? (
        <Alert variant="warning" title="File too large to display">
          This file is {formatSize(data.size)}, which exceeds the 1 MB render
          limit.
        </Alert>
      ) : data.is_binary ? (
        <Alert variant="info" title="Binary file">
          Binary file ({formatSize(data.size)}), cannot be displayed.
        </Alert>
      ) : (
        <Card>
          <CardTitle>{shortName}</CardTitle>
          <CardBody>
            {highlighted ? (
              <pre
                style={{
                  margin: 0,
                  fontSize: "0.85rem",
                  overflow: "auto",
                }}
              >
                <code
                  className="hljs"
                  // biome-ignore lint/security/noDangerouslySetInnerHtml: highlight.js output is trusted
                  dangerouslySetInnerHTML={{ __html: highlighted }}
                />
              </pre>
            ) : (
              <pre
                style={{
                  margin: 0,
                  fontSize: "0.85rem",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  overflow: "auto",
                }}
              >
                {data.content}
              </pre>
            )}
          </CardBody>
        </Card>
      )}
    </>
  );
}

export default WheelFilePage;
