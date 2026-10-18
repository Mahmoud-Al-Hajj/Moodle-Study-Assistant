import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import ExpandMoreRounded from "@mui/icons-material/ExpandMoreRounded";
import type { CourseItem, CourseSection } from "../../api/client";
import { ItemRow } from "./ItemRow";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** One accordion per section, each holding a table of its (matching) items. */
export function SectionList({
  sections,
  filtering,
  collapsed,
  onToggle,
  onPreview,
}: {
  sections: { section: CourseSection; items: CourseItem[] }[];
  filtering: boolean;
  collapsed: Set<number>;
  onToggle: (number: number) => void;
  onPreview: (item: CourseItem) => void;
}) {
  return (
    <Stack spacing={1.5}>
      {sections.map(({ section, items }) => {
        const id = `section-${section.number}`;
        const title = `${String(section.number).padStart(2, "0")} · ${section.name}`;
        return (
          <Accordion
            key={section.number}
            expanded={!collapsed.has(section.number)}
            onChange={() => onToggle(section.number)}
            disableGutters
            variant="outlined"
            slotProps={{ transition: { unmountOnExit: true } }}
            sx={{ "&::before": { display: "none" } }}
          >
            <AccordionSummary
              expandIcon={<ExpandMoreRounded />}
              id={`${id}-header`}
              aria-controls={`${id}-content`}
            >
              <Stack
                direction="row"
                spacing={2}
                sx={{ width: 1, alignItems: "baseline", pr: 1 }}
              >
                <Typography
                  variant="subtitle1"
                  component="span"
                  sx={{ flex: 1 }}
                >
                  {title}
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ whiteSpace: "nowrap" }}
                >
                  {filtering
                    ? `${items.length} of ${section.items.length}`
                    : plural(section.items.length, "item")}
                </Typography>
              </Stack>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0 }} id={`${id}-content`}>
              {items.length === 0 ? (
                <Typography color="text.secondary" sx={{ px: 2, pb: 2 }}>
                  Nothing in this section.
                </Typography>
              ) : (
                <Table size="small" aria-label={`Items in ${section.name}`}>
                  <TableHead
                    sx={{ display: { xs: "none", sm: "table-header-group" } }}
                  >
                    <TableRow>
                      <TableCell padding="checkbox" sx={{ pl: 2 }}>
                        Type
                      </TableCell>
                      <TableCell>Title</TableCell>
                      <TableCell
                        sx={{ width: (t) => t.layout.statusColumnWidth }}
                      >
                        Status
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ width: (t) => t.layout.actionsColumnWidth }}
                      />
                      {/* the action buttons carry their own labels */}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {items.map((item) => (
                      <ItemRow
                        key={item.id}
                        item={item}
                        onPreview={onPreview}
                      />
                    ))}
                  </TableBody>
                </Table>
              )}
            </AccordionDetails>
          </Accordion>
        );
      })}
    </Stack>
  );
}
