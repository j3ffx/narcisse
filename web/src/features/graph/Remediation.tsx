import { lang, t } from '@/i18n';
import { Pending } from '@/components/Pending';
import { LetterAssistant } from '@/features/assistant/LetterAssistant';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { errorMessage } from '@/lib/errors';
import { useFollowAction, useRemediation } from '@/lib/queries';
import {
  DIFFICULTY_LABELS,
  LETTER_LABELS,
  actionText,
  checkText,
  letterText,
  mailtoHref,
  requestSummary,
} from '@/lib/remediation';
import type { Action, Lang } from '@/lib/types';
import {
  CheckIcon,
  CopyIcon,
  ExternalLinkIcon,
  ListPlusIcon,
  MailIcon,
  PenLineIcon,
} from 'lucide-react';
import { Link } from 'wouter';
import { useId, useState } from 'react';
import { toast } from 'sonner';

/** What the user can do about a trace: Narcisse prepares, the user acts. */
export function Remediation({ entityId }: { entityId: number }) {
  const sheet = useRemediation(entityId);
  const id = useId();
  if (sheet.isPending) return <Pending label={t().remediation.loading} />;
  if (sheet.isError) return <p role="alert">{errorMessage(sheet.error)}</p>;
  const { actions, complaint } = sheet.data;
  if (actions.length === 0) return null;
  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-2" data-testid="remediation">
      <div>
        <h3 id={`${id}-title`} className="text-sm font-semibold">
          {t().remediation.title}
        </h3>
        <p className="text-xs text-muted-foreground">{t().remediation.intro}</p>
      </div>
      <ol className="grid gap-2">
        {actions.map((action, index) => (
          <ActionItem
            key={`${action.code}-${action.service?.name ?? index}`}
            action={action}
            entityId={entityId}
          />
        ))}
      </ol>
      <p className="text-xs text-muted-foreground">
        {t().remediation.noAnswer}{' '}
        <a
          href={complaint.url}
          target="_blank"
          rel="noreferrer noopener"
          className="underline underline-offset-2"
        >
          {t().remediation.complaint}
        </a>
      </p>
    </section>
  );
}

function ActionItem({ action, entityId }: { action: Action; entityId: number }) {
  const text = actionText(action.code);
  const service = action.service;
  const follow = useFollowAction(entityId);
  const request = action.request;
  return (
    <li className="grid gap-1.5 rounded-lg border p-3 text-sm" data-testid="action">
      <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="font-medium">{text.title}</span>
        {service && <span className="text-muted-foreground">{service.name}</span>}
        {service?.difficulty && (
          <span className="rounded bg-muted px-1.5 text-xs">
            {DIFFICULTY_LABELS[service.difficulty]}
          </span>
        )}
      </p>
      {text.what && <p className="text-muted-foreground">{text.what}</p>}
      {service?.notes && (
        <p className="text-xs">
          <span lang={service.notes_lang}>{service.notes}</span>
          {service.source === 'jdm' && (
            <span className="text-muted-foreground">
              {' '}
              (JustDeleteMe
              {service.notes_lang === 'en' && lang() === 'fr' ? ', en anglais' : ''})
            </span>
          )}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {action.url && (
          <Button asChild size="sm" variant="outline">
            <a href={action.url} target="_blank" rel="noreferrer noopener">
              <ExternalLinkIcon aria-hidden />
              {t().remediation.openPage}
            </a>
          </Button>
        )}
        {action.letter && action.letters.fr && <LetterDialog action={action} entityId={entityId} />}
        {!request && (
          <Button
            size="sm"
            variant="ghost"
            disabled={follow.isPending}
            onClick={() =>
              follow.mutate(
                { action: action.code, service: service?.name ?? '', letter: action.letter },
                { onSuccess: () => toast.success(t().remediation.added) },
              )
            }
          >
            <ListPlusIcon aria-hidden />
            {t().remediation.addToDo}
          </Button>
        )}
      </div>
      {request && (
        <p className="text-xs" data-testid="followed">
          <span className="font-medium">{t().remediation.followed}</span>
          {lang() === 'fr' ? ' : ' : ': '}
          {requestSummary(request)}
          {checkText(request) ? ` · ${checkText(request)}` : '.'}{' '}
          <Link
            href={`/profils/${request.profile_id}/a-faire`}
            className="underline underline-offset-2"
          >
            {t().remediation.seeToDo}
          </Link>
        </p>
      )}
      {action.links.length > 0 && (
        <ul className="grid gap-0.5 text-xs">
          {action.links.map((link) => (
            <li key={link.url}>
              <a
                href={link.url}
                target="_blank"
                rel="noreferrer noopener"
                className="underline underline-offset-2"
              >
                {link.title}
              </a>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

// Each language in its own words.
const LANG_LABELS: Record<Lang, string> = { fr: 'Français', en: 'English' };

/** The prepared request: the user reads it, completes it, then copies it or opens it in their
 * own mail client. */
function LetterDialog({ action, entityId }: { action: Action; entityId: number }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const follow = useFollowAction(entityId);
  const [lang, setLang] = useState<Lang>(action.lang);
  const [to, setTo] = useState(action.email ?? '');
  const [subject, setSubject] = useState(action.letters[action.lang]?.subject ?? '');
  const [body, setBody] = useState(action.letters[action.lang]?.body ?? '');
  // The text goes into a search engine's form, not into an e-mail.
  const byMail = action.letter !== 'dereference';
  const label = LETTER_LABELS[action.letter ?? ''] ?? t().remediation.request;

  const switchTo = (next: Lang) => {
    const letter = action.letters[next];
    if (!letter) return;
    setLang(next);
    setSubject(letter.subject);
    setBody(letter.body);
  };

  const copy = async (done: string) => {
    try {
      await navigator.clipboard.writeText(byMail ? letterText(subject, body, lang) : body);
      toast.success(done);
    } catch {
      toast.error(t().letters.copyFailed);
    }
  };

  const href = mailtoHref(to, subject, body);
  const cut = !href.includes('&body=');

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) switchTo(action.lang);
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <PenLineIcon aria-hidden />
          {t().remediation.prepare}
        </Button>
      </DialogTrigger>
      <DialogContent className="grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{label}</DialogTitle>
          <DialogDescription>{t().remediation.dialogIntro(byMail)}</DialogDescription>
        </DialogHeader>
        <div className="-mx-4 grid content-start gap-3 overflow-y-auto px-4">
          <div role="group" aria-label={t().remediation.letterLang} className="flex gap-2">
            {(['fr', 'en'] as const).map((option) => (
              <Button
                key={option}
                size="sm"
                variant={lang === option ? 'secondary' : 'ghost'}
                aria-pressed={lang === option}
                onClick={() => switchTo(option)}
              >
                {LANG_LABELS[option]}
              </Button>
            ))}
          </div>
          {byMail && (
            <>
              <div className="grid gap-1">
                <Label htmlFor={`${id}-to`}>{t().remediation.recipient}</Label>
                <Input
                  id={`${id}-to`}
                  type="email"
                  value={to}
                  placeholder={t().remediation.recipientHint}
                  onChange={(e) => setTo(e.target.value)}
                />
              </div>
              <div className="grid gap-1">
                <Label htmlFor={`${id}-subject`}>{t().remediation.subject}</Label>
                <Input
                  id={`${id}-subject`}
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                />
              </div>
            </>
          )}
          <LetterAssistant
            entityId={entityId}
            subject={subject}
            body={body}
            onTake={(nextSubject, nextBody) => {
              if (byMail) setSubject(nextSubject);
              setBody(nextBody);
            }}
            onRestore={() => switchTo(lang)}
          />
          <div className="grid gap-1">
            <Label htmlFor={`${id}-body`}>{t().remediation.text}</Label>
            <textarea
              id={`${id}-body`}
              value={body}
              rows={14}
              onChange={(e) => setBody(e.target.value)}
              className="w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => void copy(t().letters.copied)}>
            <CopyIcon aria-hidden />
            {t().letters.copy}
          </Button>
          {byMail && (
            <Button asChild>
              <a
                href={href}
                onClick={() => {
                  if (cut) void copy(t().letters.copiedPaste);
                }}
              >
                <MailIcon aria-hidden />
                {t().letters.openMail}
              </a>
            </Button>
          )}
          <Button
            variant="secondary"
            disabled={follow.isPending}
            onClick={() =>
              follow.mutate(
                {
                  action: action.code,
                  service: action.service?.name ?? '',
                  letter: action.letter,
                  recipient: to.trim() || null,
                  subject: byMail ? subject : null,
                  body,
                  status: 'sent',
                },
                {
                  onSuccess: () => {
                    setOpen(false);
                    toast.success(t().remediation.followedToast);
                  },
                },
              )
            }
          >
            <CheckIcon aria-hidden />
            {t().remediation.sent}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
