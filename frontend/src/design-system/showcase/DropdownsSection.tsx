import { useState } from "react";
import {
  Button,
  CheckboxDropdown,
  Combobox,
  CountrySelect,
  Dialog,
  Divider,
  FormField,
  FormLayout,
  MultiSelect,
  NationalitySelect,
  OverflowMenu,
  PersonSelect,
  RadioDropdown,
  SectionCard,
  Select,
  SplitButton,
  Stack,
  TreeSelect,
} from "../index";
import { coverageRows } from "./coverage";

const desks = [
  { value: "north", label: "North operations" },
  { value: "harbour", label: "Harbour desk" },
  {
    value: "west",
    label: "West intake with a very long authorized desk label that must wrap",
  },
];

const grouped = [
  { value: "open", label: "Open", group: "Status" },
  { value: "review", label: "In review", group: "Status" },
  { value: "north", label: "North", group: "Desk" },
  { value: "harbour", label: "Harbour", group: "Desk" },
];

const tree = [
  {
    value: "north",
    label: "North branch",
    children: [
      { value: "mgr", label: "Managers" },
      { value: "coord", label: "Coordinators" },
    ],
  },
  {
    value: "harbour",
    label: "Harbour branch",
    children: [{ value: "intake", label: "Intake" }],
  },
];

export function DropdownsSection() {
  const [standard, setStandard] = useState("north");
  const [compact, setCompact] = useState("harbour");
  const [searchable, setSearchable] = useState("north");
  const [country, setCountry] = useState("AE");
  const [nationality, setNationality] = useState("IN");
  const [groupedValue, setGroupedValue] = useState("open");
  const [multi, setMulti] = useState<string[]>(["harbour"]);
  const [parent, setParent] = useState("");
  const [created, setCreated] = useState("");
  const [createOptions, setCreateOptions] = useState(desks);
  const [child, setChild] = useState("");
  const [asyncValue, setAsyncValue] = useState("");
  const [asyncQuery, setAsyncQuery] = useState("");
  const [asyncLoading, setAsyncLoading] = useState(false);
  const [asyncOptions, setAsyncOptions] = useState(desks);
  const [invalid, setInvalid] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [treeValue, setTreeValue] = useState("mgr");
  const [person, setPerson] = useState("rahman");
  const [checks, setChecks] = useState<string[]>(["open"]);
  const [radio, setRadio] = useState("review");

  const loadAsync = (query: string) => {
    setAsyncLoading(true);
    window.setTimeout(() => {
      setAsyncOptions(
        desks.filter((item) =>
          item.label.toLowerCase().includes(query.toLowerCase()),
        ),
      );
      setAsyncLoading(false);
    }, 350);
  };

  return (
    <section id="dropdowns" className="ds-stack-20">
      <SectionCard
        title="Dropdowns and selection"
        description="Portaled lists with compact triggers, light-violet hover, and a restrained selected state."
      >
        <FormLayout columns={2}>
          <FormField label="Standard" htmlFor="dd-standard">
            <Select
              id="dd-standard"
              options={desks}
              value={standard}
              onChange={setStandard}
            />
          </FormField>
          <FormField label="Compact" htmlFor="dd-compact">
            <Select
              id="dd-compact"
              compact
              options={desks}
              value={compact}
              onChange={setCompact}
            />
          </FormField>
          <FormField label="Searchable" htmlFor="dd-search">
            <Combobox
              id="dd-search"
              options={desks}
              value={searchable}
              onChange={setSearchable}
            />
          </FormField>
          <FormField label="Country" htmlFor="dd-country" required>
            <CountrySelect
              id="dd-country"
              value={country}
              onChange={setCountry}
            />
          </FormField>
          <FormField label="Nationality" htmlFor="dd-nationality">
            <NationalitySelect
              id="dd-nationality"
              value={nationality}
              onChange={setNationality}
            />
          </FormField>
          <FormField label="Grouped options" htmlFor="dd-group">
            <Select
              id="dd-group"
              options={grouped}
              value={groupedValue}
              onChange={setGroupedValue}
            />
          </FormField>
          <FormField label="Multi-select" htmlFor="dd-multi">
            <MultiSelect
              id="dd-multi"
              options={desks}
              value={multi}
              onChange={setMulti}
            />
          </FormField>
          <FormField label="Desk" htmlFor="dd-parent">
            <Select
              id="dd-parent"
              options={desks.slice(0, 2)}
              value={parent}
              onChange={(value) => {
                setParent(value);
                setChild("");
              }}
            />
          </FormField>
          <FormField
            label="Dependent owner"
            htmlFor="dd-child"
            hint="Disabled until a desk is selected."
          >
            <Select
              id="dd-child"
              options={[
                { value: "rahman", label: "A. Rahman" },
                { value: "khalid", label: "M. Khalid" },
              ]}
              value={child}
              onChange={setChild}
              disabled={!parent}
              unavailable={!parent}
            />
          </FormField>
          <FormField label="Async / loading" htmlFor="dd-async">
            <Combobox
              id="dd-async"
              options={asyncOptions}
              value={asyncValue}
              onChange={setAsyncValue}
              loading={asyncLoading}
              query={asyncQuery}
              onQueryChange={(next) => {
                setAsyncQuery(next);
                loadAsync(next);
              }}
              emptyLabel="No matching desks"
            />
          </FormField>
          <FormField label="Empty results" htmlFor="dd-empty">
            <Combobox
              id="dd-empty"
              options={[]}
              value=""
              onChange={() => undefined}
              emptyLabel="No matching desks"
            />
          </FormField>
          <FormField
            label="Creatable"
            htmlFor="dd-create"
            hint="Optional controlled mode. Feature code owns the new value."
          >
            <Combobox
              id="dd-create"
              options={createOptions}
              value={created}
              onChange={setCreated}
              creatable
              onCreate={(query) => {
                setCreateOptions((current) => [
                  ...current,
                  { value: query.toLowerCase(), label: query },
                ]);
                setCreated(query.toLowerCase());
              }}
            />
          </FormField>
          <FormField
            label="Validation error"
            htmlFor="dd-invalid"
            error="Select an authorized desk."
          >
            <Select
              id="dd-invalid"
              options={desks}
              value={invalid}
              onChange={setInvalid}
              invalid
            />
          </FormField>
          <FormField label="Disabled" htmlFor="dd-disabled">
            <Select id="dd-disabled" options={desks} value="north" disabled />
          </FormField>
          <FormField label="Read only" htmlFor="dd-readonly">
            <Select id="dd-readonly" options={desks} value="harbour" readOnly />
          </FormField>
          <FormField label="Person" htmlFor="dd-person">
            <PersonSelect
              id="dd-person"
              value={person}
              onChange={setPerson}
              people={[
                { value: "rahman", name: "A. Rahman", subtitle: "Manager" },
                { value: "khalid", name: "M. Khalid", subtitle: "Team leader" },
              ]}
            />
          </FormField>
          <FormField label="Tree select" htmlFor="dd-tree">
            <TreeSelect
              id="dd-tree"
              options={tree}
              value={treeValue}
              onChange={setTreeValue}
            />
          </FormField>
          <FormField label="Checkbox dropdown" htmlFor="dd-check">
            <CheckboxDropdown
              id="dd-check"
              options={[
                { value: "open", label: "Open" },
                { value: "review", label: "Review" },
              ]}
              value={checks}
              onChange={setChecks}
            />
          </FormField>
          <FormField label="Radio dropdown" htmlFor="dd-radio">
            <RadioDropdown
              id="dd-radio"
              options={[
                { value: "open", label: "Open" },
                { value: "review", label: "Review" },
              ]}
              value={radio}
              onChange={setRadio}
            />
          </FormField>
        </FormLayout>
        <Divider />
        <Stack gap={12}>
          <div className="ds-cluster">
            <Button variant="secondary" onClick={() => setDialogOpen(true)}>
              Dropdown in dialog
            </Button>
            <SplitButton
              label="Create"
              onClick={() => undefined}
              items={[
                { id: "record", label: "Record" },
                { id: "export", label: "Export" },
              ]}
            />
            <OverflowMenu
              items={[
                { id: "columns", label: "Columns" },
                { id: "export", label: "Export" },
              ]}
            />
          </div>
          <div className="ds-placement-well">
            <FormField label="Opens upward near the bottom" htmlFor="dd-flip">
              <Select
                id="dd-flip"
                options={desks}
                value={standard}
                onChange={setStandard}
              />
            </FormField>
          </div>
        </Stack>
      </SectionCard>
      <Dialog
        open={dialogOpen}
        title="Assign desk"
        onClose={() => setDialogOpen(false)}
        footer={<Button onClick={() => setDialogOpen(false)}>Done</Button>}
      >
        <FormField label="Desk" htmlFor="dd-dialog">
          <Combobox
            id="dd-dialog"
            options={desks}
            value={searchable}
            onChange={setSearchable}
          />
        </FormField>
      </Dialog>
      <SectionCard
        id="coverage"
        title="Component coverage"
        description="Ready means the primitive can be used on a migrated page. Feature code still owns data and permissions."
      >
        <div className="ds-scroll">
          <table className="ds-coverage">
            <thead>
              <tr>
                <th>Component</th>
                <th>States</th>
                <th>Responsive</th>
                <th>Keyboard</th>
                <th>Use</th>
                <th>Migration</th>
              </tr>
            </thead>
            <tbody>
              {coverageRows.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td>{row.states}</td>
                  <td>{row.responsive}</td>
                  <td>{row.keyboard}</td>
                  <td>{row.use}</td>
                  <td>{row.ready}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </section>
  );
}
