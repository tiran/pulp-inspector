import {
  Alert,
  Breadcrumb,
  BreadcrumbItem,
  CardBody,
  Label,
  Pagination,
  Spinner,
  Switch,
  Tab,
  TabContent,
  TabContentBody,
  TabTitleText,
  Tabs,
  Title,
} from "@patternfly/react-core";
import {
  ExpandableRowContent,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@patternfly/react-table";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

interface WheelFileEntry {
  filename: string;
  file_size: number;
  compress_size: number;
  crc32: number;
}

interface WheelInspectResponse {
  wheel_filename: string;
  wheel_url: string;
  files: WheelFileEntry[];
  metadata: string | null;
}

type CompareStatus =
  | "match"
  | "different"
  | "pulp_only"
  | "pypi_only"
  | "fromager";

interface CompareFileEntry {
  filename: string;
  status: CompareStatus;
  pulp_size: number | null;
  pulp_crc32: number | null;
  pypi_size: number | null;
  pypi_crc32: number | null;
}

interface WheelCompareResponse {
  pulp_filename: string;
  pulp_wheel_url: string;
  pypi_filename: string | null;
  pypi_url: string | null;
  pypi_project_url: string | null;
  pypi_version: string | null;
  files: CompareFileEntry[];
  summary: Record<string, number>;
}

interface FileDiffResponse {
  filepath: string;
  is_binary: boolean;
  diff: string;
  pulp_filename: string;
  pypi_filename: string;
}

function DiffView({ diff, isBinary }: { diff: string; isBinary: boolean }) {
  if (isBinary) {
    return <em>Binary files differ</em>;
  }
  if (!diff) {
    return <em>Files are identical</em>;
  }
  return (
    <pre
      style={{
        fontSize: "0.8rem",
        margin: 0,
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
        lineHeight: 1.5,
      }}
    >
      {diff.split("\n").map((line, i) => {
        let bg = "transparent";
        if (line.startsWith("+") && !line.startsWith("+++")) bg = "#e6ffec";
        else if (line.startsWith("-") && !line.startsWith("---"))
          bg = "#ffebe9";
        else if (line.startsWith("@@")) bg = "#ddf4ff";
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: diff lines can be duplicated
          <div key={i} style={{ backgroundColor: bg }}>
            {line}
          </div>
        );
      })}
    </pre>
  );
}

const BINARY_EXTENSIONS = new Set([
  ".so",
  ".dylib",
  ".dll",
  ".pyd",
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".ico",
  ".webp",
  ".woff",
  ".woff2",
  ".ttf",
  ".eot",
  ".otf",
  ".zip",
  ".gz",
  ".bz2",
  ".xz",
  ".zst",
  ".tar",
  ".pyc",
  ".pyo",
  ".pyd",
  ".o",
  ".a",
  ".lib",
]);

function isTextFile(filename: string): boolean {
  const lower = filename.toLowerCase();
  return !BINARY_EXTENSIONS.has(lower.slice(lower.lastIndexOf(".")));
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatCrc32(crc: number): string {
  return crc.toString(16).padStart(8, "0").toUpperCase();
}

function StatusLabel({ status }: { status: CompareStatus }) {
  switch (status) {
    case "match":
      return <Label color="green">match</Label>;
    case "different":
      return <Label color="orange">different</Label>;
    case "pulp_only":
      return <Label color="blue">pulp only</Label>;
    case "pypi_only":
      return <Label color="yellow">pypi only</Label>;
    case "fromager":
      return <Label color="purple">fromager</Label>;
  }
}

function WheelPage() {
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
  const indexPrefix = `/indexes/${name}/${version}/${variant}`;
  const wheelPath = `${indexPrefix}/packages/${packageName}/${filename}`;
  const [data, setData] = useState<WheelInspectResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string | number>("files");

  // Compare tab state (lazy-loaded)
  const [compareData, setCompareData] = useState<WheelCompareResponse | null>(
    null,
  );
  const [compareError, setCompareError] = useState<string | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [diffOnly, setDiffOnly] = useState(true);
  const compareFetched = useRef(false);

  // Pagination state
  const [filesPage, setFilesPage] = useState(1);
  const [filesPerPage, setFilesPerPage] = useState(100);
  const [comparePage, setComparePage] = useState(1);
  const [comparePerPage, setComparePerPage] = useState(100);

  // Expandable diff state: keyed by filepath
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [diffs, setDiffs] = useState<Record<string, FileDiffResponse>>({});
  const [diffLoading, setDiffLoading] = useState<Set<string>>(new Set());

  const toggleExpand = useCallback(
    (filepath: string) => {
      setExpandedFiles((prev) => {
        const next = new Set(prev);
        if (next.has(filepath)) {
          next.delete(filepath);
        } else {
          next.add(filepath);
          // Fetch diff if not yet loaded
          if (!diffs[filepath] && !diffLoading.has(filepath)) {
            setDiffLoading((dl) => new Set(dl).add(filepath));
            fetch(`/api${wheelPath}/compare/diff/${filepath}`)
              .then((res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json() as Promise<FileDiffResponse>;
              })
              .then((data) =>
                setDiffs((prev) => ({ ...prev, [filepath]: data })),
              )
              .catch(() =>
                setDiffs((prev) => ({
                  ...prev,
                  [filepath]: {
                    filepath,
                    is_binary: false,
                    diff: "Error loading diff",
                    pulp_filename: "",
                    pypi_filename: "",
                  },
                })),
              )
              .finally(() =>
                setDiffLoading((dl) => {
                  const next = new Set(dl);
                  next.delete(filepath);
                  return next;
                }),
              );
          }
        }
        return next;
      });
    },
    [diffs, diffLoading, wheelPath],
  );

  useEffect(() => {
    if (!name || !packageName || !filename) return;
    setLoading(true);
    fetch(`/api${wheelPath}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<WheelInspectResponse>;
      })
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [name, wheelPath, packageName, filename]);

  // Lazy-fetch comparison data when tab is activated
  useEffect(() => {
    if (activeTab !== "compare" || compareFetched.current) return;
    compareFetched.current = true;
    setCompareLoading(true);
    fetch(`/api${wheelPath}/compare`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<WheelCompareResponse>;
      })
      .then(setCompareData)
      .catch((err) => setCompareError(String(err)))
      .finally(() => setCompareLoading(false));
  }, [activeTab, wheelPath]);

  if (loading) return <Spinner aria-label="Inspecting wheel" />;
  if (error)
    return (
      <Alert variant="danger" title="Error inspecting wheel">
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
        <BreadcrumbItem isActive>{filename}</BreadcrumbItem>
      </Breadcrumb>

      <Title headingLevel="h1" style={{ marginBottom: "1rem" }}>
        {filename}
      </Title>

      <Tabs
        activeKey={activeTab}
        onSelect={(_event, tabKey) => setActiveTab(tabKey)}
        aria-label="Wheel inspection tabs"
      >
        <Tab
          eventKey="files"
          title={<TabTitleText>Files ({data.files.length})</TabTitleText>}
        >
          <TabContent id="tab-files">
            <TabContentBody>
              <CardBody>
                <Pagination
                  itemCount={data.files.length}
                  perPage={filesPerPage}
                  page={filesPage}
                  perPageOptions={[
                    { title: "50", value: 50 },
                    { title: "100", value: 100 },
                    { title: "500", value: 500 },
                  ]}
                  onSetPage={(_e, p) => setFilesPage(p)}
                  onPerPageSelect={(_e, pp) => {
                    setFilesPerPage(pp);
                    setFilesPage(1);
                  }}
                  isCompact
                  style={{ marginBottom: "0.5rem" }}
                />
                <Table aria-label="Wheel file listing" variant="compact">
                  <Thead>
                    <Tr>
                      <Th>Filename</Th>
                      <Th>Size</Th>
                      <Th>Compressed</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {data.files
                      .slice(
                        (filesPage - 1) * filesPerPage,
                        filesPage * filesPerPage,
                      )
                      .map((f) => (
                        <Tr key={f.filename}>
                          <Td dataLabel="Filename">
                            <Link to={`${wheelPath}/files/${f.filename}`}>
                              <code>{f.filename}</code>
                            </Link>
                          </Td>
                          <Td dataLabel="Size">{formatSize(f.file_size)}</Td>
                          <Td dataLabel="Compressed">
                            {formatSize(f.compress_size)}
                          </Td>
                        </Tr>
                      ))}
                  </Tbody>
                </Table>
              </CardBody>
            </TabContentBody>
          </TabContent>
        </Tab>

        <Tab
          eventKey="metadata"
          title={<TabTitleText>METADATA</TabTitleText>}
          isDisabled={!data.metadata}
        >
          <TabContent id="tab-metadata">
            <TabContentBody>
              <CardBody>
                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    fontSize: "0.85rem",
                    margin: 0,
                  }}
                >
                  {data.metadata}
                </pre>
              </CardBody>
            </TabContentBody>
          </TabContent>
        </Tab>

        <Tab
          eventKey="compare"
          title={<TabTitleText>Compare with PyPI</TabTitleText>}
        >
          <TabContent id="tab-compare">
            <TabContentBody>
              <CardBody>
                {compareLoading && <Spinner aria-label="Comparing with PyPI" />}
                {compareError && (
                  <Alert variant="danger" title="Error comparing with PyPI">
                    {compareError}
                  </Alert>
                )}
                {compareData && !compareData.pypi_filename && (
                  <Alert
                    variant="info"
                    title="No matching wheel found on PyPI"
                    isInline
                  >
                    No wheel matching version {compareData.pypi_version} was
                    found on PyPI.org for this package.
                  </Alert>
                )}
                {compareData?.pypi_filename && (
                  <>
                    <div style={{ marginBottom: "1rem" }}>
                      <div>
                        <strong>Pulp:</strong>{" "}
                        <code>{compareData.pulp_filename}</code>{" "}
                        <a
                          href={compareData.pulp_wheel_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          download
                        </a>
                      </div>
                      <div>
                        <strong>PyPI:</strong>{" "}
                        <code>{compareData.pypi_filename}</code>{" "}
                        <a
                          href={compareData.pypi_url ?? ""}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          download
                        </a>
                        {compareData.pypi_project_url && (
                          <>
                            {" | "}
                            <a
                              href={compareData.pypi_project_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              PyPI project page
                            </a>
                          </>
                        )}
                      </div>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        gap: "1rem",
                        marginBottom: "1rem",
                        flexWrap: "wrap",
                      }}
                    >
                      <Label color="green">
                        {compareData.summary.match ?? 0} matching
                      </Label>
                      <Label color="orange">
                        {compareData.summary.different ?? 0} different
                      </Label>
                      <Label color="blue">
                        {compareData.summary.pulp_only ?? 0} Pulp-only
                      </Label>
                      <Label color="yellow">
                        {compareData.summary.pypi_only ?? 0} PyPI-only
                      </Label>
                      <Label color="purple">
                        {compareData.summary.fromager ?? 0} fromager
                      </Label>
                    </div>
                    <div style={{ marginBottom: "1rem" }}>
                      <Switch
                        id="diff-only-toggle"
                        label="Show differences only"
                        isChecked={diffOnly}
                        onChange={(_event, checked) => {
                          setDiffOnly(checked);
                          setComparePage(1);
                        }}
                      />
                    </div>
                    {(() => {
                      const filtered = compareData.files.filter(
                        (f) =>
                          !diffOnly ||
                          (f.status !== "match" && f.status !== "fromager"),
                      );
                      const paged = filtered.slice(
                        (comparePage - 1) * comparePerPage,
                        comparePage * comparePerPage,
                      );
                      return (
                        <>
                          <Pagination
                            itemCount={filtered.length}
                            perPage={comparePerPage}
                            page={comparePage}
                            perPageOptions={[
                              { title: "50", value: 50 },
                              { title: "100", value: 100 },
                              { title: "500", value: 500 },
                            ]}
                            onSetPage={(_e, p) => setComparePage(p)}
                            onPerPageSelect={(_e, pp) => {
                              setComparePerPage(pp);
                              setComparePage(1);
                            }}
                            isCompact
                            style={{ marginBottom: "0.5rem" }}
                          />
                          <Table
                            aria-label="Wheel comparison with PyPI"
                            variant="compact"
                          >
                            <Thead>
                              <Tr>
                                <Th />
                                <Th>Filename</Th>
                                <Th>Status</Th>
                                <Th>Pulp Size</Th>
                                <Th>PyPI Size</Th>
                                <Th>Pulp CRC32</Th>
                                <Th>PyPI CRC32</Th>
                              </Tr>
                            </Thead>
                            {paged.map((f, rowIndex) => {
                              const canExpand =
                                f.status === "different" &&
                                isTextFile(f.filename);
                              const isExpanded = expandedFiles.has(f.filename);
                              return (
                                <Tbody key={f.filename} isExpanded={isExpanded}>
                                  <Tr>
                                    <Td
                                      expand={
                                        canExpand
                                          ? {
                                              rowIndex,
                                              isExpanded,
                                              onToggle: () =>
                                                toggleExpand(f.filename),
                                            }
                                          : undefined
                                      }
                                    />
                                    <Td dataLabel="Filename">
                                      <code>{f.filename}</code>
                                    </Td>
                                    <Td dataLabel="Status">
                                      <StatusLabel status={f.status} />
                                    </Td>
                                    <Td dataLabel="Pulp Size">
                                      {f.pulp_size != null
                                        ? formatSize(f.pulp_size)
                                        : "-"}
                                    </Td>
                                    <Td dataLabel="PyPI Size">
                                      {f.pypi_size != null
                                        ? formatSize(f.pypi_size)
                                        : "-"}
                                    </Td>
                                    <Td dataLabel="Pulp CRC32">
                                      {f.pulp_crc32 != null ? (
                                        <code>{formatCrc32(f.pulp_crc32)}</code>
                                      ) : (
                                        "-"
                                      )}
                                    </Td>
                                    <Td dataLabel="PyPI CRC32">
                                      {f.pypi_crc32 != null ? (
                                        <code>{formatCrc32(f.pypi_crc32)}</code>
                                      ) : (
                                        "-"
                                      )}
                                    </Td>
                                  </Tr>
                                  {canExpand && (
                                    <Tr isExpanded={isExpanded}>
                                      <Td colSpan={7}>
                                        <ExpandableRowContent>
                                          {diffLoading.has(f.filename) && (
                                            <Spinner
                                              size="md"
                                              aria-label="Loading diff"
                                            />
                                          )}
                                          {diffs[f.filename] && (
                                            <DiffView
                                              diff={diffs[f.filename].diff}
                                              isBinary={
                                                diffs[f.filename].is_binary
                                              }
                                            />
                                          )}
                                        </ExpandableRowContent>
                                      </Td>
                                    </Tr>
                                  )}
                                </Tbody>
                              );
                            })}
                          </Table>
                        </>
                      );
                    })()}
                  </>
                )}
              </CardBody>
            </TabContentBody>
          </TabContent>
        </Tab>
      </Tabs>
    </>
  );
}

export default WheelPage;
