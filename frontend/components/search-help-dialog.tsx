import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { HelpCircle, Search, Type, Code, CheckCircle2 } from "lucide-react";
import { useTranslations } from "next-intl";

export function SearchHelpDialog() {
  const t = useTranslations("NotificationLog");

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button type="button" size="sm" variant="ghost" className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground" title={t('searchSyntaxHelp')}>
          <HelpCircle className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[650px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Search className="h-5 w-5 text-primary" />
            {t('searchHelp.title')}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <p className="text-sm text-muted-foreground">
            {t('searchHelp.intro')}
          </p>

          {/* Logic Operators */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              {t('searchHelp.booleanHeading')}
            </h3>
            <div className="bg-muted/50 rounded-md p-3 text-sm space-y-2 border">
              <p>
                {t.rich('searchHelp.booleanDesc', {
                  code: (chunks) => <code className="text-primary font-bold">{chunks}</code>,
                })}
              </p>
              <div className="bg-background p-2.5 rounded border border-border/50 font-mono text-xs">
                (sender:github <span className="text-primary font-bold">AND</span> severity:error) <span className="text-primary font-bold">OR</span> <span className="text-primary font-bold">NOT</span> tag:dev
              </div>
            </div>
          </div>

          {/* Fields */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Type className="h-4 w-4 text-blue-500" />
              {t('searchHelp.fieldsHeading')}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <FieldCard name="title:" desc={t('searchHelp.fieldTitleDesc')} example="title:failed" />
              <FieldCard name="message:" desc={t('searchHelp.fieldMessageDesc')} example="message:timeout" />
              <FieldCard name="sender:" desc={t('searchHelp.fieldSenderDesc')} example="sender:gitlab" />
              <FieldCard name="severity:" desc={t('searchHelp.fieldSeverityDesc')} example="severity:error" />
              <FieldCard name="tag:" desc={t('searchHelp.fieldTagDesc')} example="tag:production" />
              <FieldCard name="after: / before:" desc={t('searchHelp.fieldTimeDesc')} example="after:1h before:1d" />
            </div>
            <p className="text-xs text-muted-foreground mt-1">{t('searchHelp.noFieldNote')}</p>
          </div>

          {/* Matching Types */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Code className="h-4 w-4 text-amber-500" />
              {t('searchHelp.matchingHeading')}
            </h3>
            <div className="space-y-3">
              <div className="flex gap-3 items-start border rounded-md p-3 bg-muted/20">
                <div className="font-mono text-xs bg-background border px-2 py-1 rounded mt-0.5">unquoted</div>
                <div className="text-sm">
                  <p className="font-medium">{t('searchHelp.partialTitle')}</p>
                  <p className="text-muted-foreground text-xs mt-0.5">{t('searchHelp.partialDesc')}</p>
                  <p className="font-mono text-xs mt-1 text-foreground">sender:git <span className="text-muted-foreground ml-2">{t('searchHelp.partialComment')}</span></p>
                </div>
              </div>

              <div className="flex gap-3 items-start border rounded-md p-3 bg-emerald-500/10 border-emerald-500/20">
                <div className="font-mono text-xs bg-background border border-emerald-500/30 text-emerald-500 px-2 py-1 rounded mt-0.5">"quoted"</div>
                <div className="text-sm">
                  <p className="font-medium text-emerald-700 dark:text-emerald-400">{t('searchHelp.exactTitle')}</p>
                  <p className="text-muted-foreground text-xs mt-0.5">{t('searchHelp.exactDesc')}</p>
                  <p className="font-mono text-xs mt-1 text-emerald-600 dark:text-emerald-400">sender:"github" <span className="opacity-70 ml-2">{t('searchHelp.exactComment')}</span></p>
                </div>
              </div>

              <div className="flex gap-3 items-start border rounded-md p-3 bg-amber-500/10 border-amber-500/20">
                <div className="font-mono text-xs bg-background border border-amber-500/30 text-amber-500 px-2 py-1 rounded mt-0.5">/regex/</div>
                <div className="text-sm">
                  <p className="font-medium text-amber-700 dark:text-amber-400">{t('searchHelp.regexTitle')}</p>
                  <p className="text-muted-foreground text-xs mt-0.5">{t('searchHelp.regexDesc')}</p>
                  <p className="font-mono text-xs mt-1 text-amber-600 dark:text-amber-400">message:/error|failed/ <span className="opacity-70 ml-2">{t('searchHelp.regexComment')}</span></p>
                </div>
              </div>
            </div>
          </div>

        </div>
      </DialogContent>
    </Dialog>
  );
}

function FieldCard({ name, desc, example }: { name: string; desc: string; example: string }) {
  return (
    <div className="border border-border/50 bg-muted/30 p-2.5 rounded-md flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs font-bold text-blue-500">{name}</span>
      </div>
      <p className="text-xs text-muted-foreground">{desc}</p>
      <div className="font-mono text-[10px] bg-background border px-1.5 py-1 rounded text-foreground w-fit">
        {example}
      </div>
    </div>
  );
}
