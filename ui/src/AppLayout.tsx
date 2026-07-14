import {
  Button,
  Masthead,
  MastheadBrand,
  MastheadContent,
  MastheadMain,
  MastheadToggle,
  Nav,
  NavItem,
  NavList,
  Page,
  PageSection,
  PageSidebar,
  PageSidebarBody,
  PageToggleButton,
  Toolbar,
  ToolbarContent,
  ToolbarItem,
} from "@patternfly/react-core";
import { BarsIcon, RedoIcon } from "@patternfly/react-icons";
import { useCallback, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

function AppLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const onClearCache = useCallback(() => {
    fetch("/api/cache/clear", { method: "POST" }).then(() => {
      window.location.reload();
    });
  }, []);

  const onNavSelect = (
    _event: React.FormEvent<HTMLInputElement>,
    result: { itemId: number | string },
  ) => {
    navigate(String(result.itemId));
  };

  const masthead = (
    <Masthead>
      <MastheadMain>
        <MastheadToggle>
          <PageToggleButton
            variant="plain"
            aria-label="Global navigation"
            isSidebarOpen={isSidebarOpen}
            onSidebarToggle={() => setIsSidebarOpen(!isSidebarOpen)}
          >
            <BarsIcon />
          </PageToggleButton>
        </MastheadToggle>
        <MastheadBrand>Pulp Inspector</MastheadBrand>
      </MastheadMain>
      <MastheadContent>
        <Toolbar>
          <ToolbarContent>
            <ToolbarItem align={{ default: "alignEnd" }}>
              <Button
                variant="plain"
                onClick={onClearCache}
                icon={<RedoIcon />}
                title="Clear caches"
              >
                Refresh
              </Button>
            </ToolbarItem>
          </ToolbarContent>
        </Toolbar>
      </MastheadContent>
    </Masthead>
  );

  const sidebar = (
    <PageSidebar isSidebarOpen={isSidebarOpen}>
      <PageSidebarBody>
        <Nav onSelect={onNavSelect} aria-label="Navigation">
          <NavList>
            <NavItem itemId="/" isActive={location.pathname === "/"}>
              Browse Indexes
            </NavItem>
          </NavList>
        </Nav>
      </PageSidebarBody>
    </PageSidebar>
  );

  return (
    <Page masthead={masthead} sidebar={sidebar}>
      <PageSection>
        <Outlet />
      </PageSection>
    </Page>
  );
}

export default AppLayout;
