/*
 * sctl engine
 *
 * IO engine using the Linux ioctl based interface for NVMe device
 * This ioengine operates in sync mode with block devices (/dev/nvmeX)
 *
 */
#include <sys/stat.h>
#include "../fio.h"
#include "../optgroup.h"

struct sctl_data {
	struct copy_range *cr;
	char *buffer;
};

struct sctl_options {
	struct thread_data *td;
	unsigned int emulate;
};

static struct fio_option options[] = {
	{
		.name	= "emulate",
		.lname	= "Emulate simple copy commands",
		.type	= FIO_OPT_BOOL,
		.off1	= offsetof(struct sctl_options, emulate),
		.help	= "Emulate simple copy commands",
		.def	= "0",
		.category = FIO_OPT_C_ENGINE,
		.group	= FIO_OPT_G_IO_TYPE,
	},
	{
		.name	= NULL,
	},
};

static int fio_sctl_emulate(struct thread_data *td, struct io_u *io_u)
{
	struct sctl_data *sd = td->io_ops_data;
	struct copy_range *cr = sd->cr;
	struct range_entry *range = (struct range_entry *)cr->ranges;
	struct fio_file *f = io_u->file;
	struct thread_options *o = &td->o;
	char *buffer = sd->buffer;
	int i, ret;
	uint64_t bytes;

	for (i = 0; i < cr->nr_range; i++) {
		bytes = range[i].len;
		assert(bytes == o->bs[DDIR_COPY]);
		ret = pread(f->fd, buffer, bytes, range[i].src);
		dprint(FD_IO, "sctl: read range %d, offset=0x%llx, len=0x%lx, ret=%d\n",
				i, range[i].src, bytes, ret);
		if (ret < 0) {
			range[i].comp_len = 0;
			return ret;
		}
		assert(ret == bytes);

		ret = pwrite(f->fd, sd->buffer, bytes, range[i].dst);
		dprint(FD_IO, "sctl: write offset=0x%llx, len=0x%lx\n, ret=%d\n",
				range[i].dst, bytes, ret);
		if (ret < 0) {
			range[i].comp_len = 0;
			return ret;
		}

		if (ret != bytes) {
			range[i].comp_len = ret;
			return ret;
		}

		range[i].comp_len = bytes;
	}

	return 0;
}

static enum fio_q_status fio_sctl_queue(struct thread_data *td,
					struct io_u *io_u)
{
	struct sctl_options *eo = td->eo;
	struct sctl_data *sd = td->io_ops_data;
	struct copy_range *cr = sd->cr;
	struct fio_file *f = io_u->file;
	int i, ret;

	dprint(FD_IO, "sctl: cr->nr_range = %llu\n", cr->nr_range);
	for (i = 0; i < cr->nr_range; i++) {
		dprint(FD_IO, "sctl: cr->ranges[%d].src = %llu\n", i, cr->ranges[i].src);
		dprint(FD_IO, "sctl: cr->ranges[%d].dst = %llu\n", i, cr->ranges[i].dst);
		dprint(FD_IO, "sctl: cr->ranges[%d].len = %llu\n", i, cr->ranges[i].len);
	}

	if (eo->emulate)
		ret = fio_sctl_emulate(td, io_u);
	else
		ret = ioctl(f->fd, BLKCOPY, cr);

	if (ret > 0) {
		dprint(FD_IO, "sctl: BLKCOPY IOCTL returned %d, errno = %d\n", ret, errno);
		ret *= -1;
		if (!errno)
			errno = EIO;
	}

	if (ret < 0) {
		io_u->error = errno;
		td_verror(td, io_u->error, "xfer");
	}

	return FIO_Q_COMPLETED;
}

static int fio_sctl_prep(struct thread_data *td, struct io_u *io_u)
{
	struct sctl_data *sd = td->io_ops_data;
	struct copy_range *cr = sd->cr;

	memset(cr, 0, sizeof(*cr));

	cr->nr_range = io_u->xfer_buflen / sizeof(struct range_entry);
	cr->reserved = 0;
	memcpy(&cr->ranges[0], io_u->xfer_buf, io_u->xfer_buflen);

	return 0;
}

static void fio_sctl_cleanup(struct thread_data *td)
{
	struct sctl_data *sd = td->io_ops_data;
	struct thread_options *o = &td->o;

	if (sd) {
		if (sd->buffer)
			fio_memfree(sd->buffer, o->bs[DDIR_COPY], false);
		free(sd->cr);
		free(sd);
	}
}

static int fio_sctl_init(struct thread_data *td)
{
	struct thread_options *o = &td->o;
	struct sctl_data *sd;
	struct sctl_options *eo = td->eo;

	sd = calloc(1, sizeof(*sd));
	sd->cr = calloc(1, sizeof(*sd->cr) + (sizeof(struct range_entry)*o->num_range));

	if (eo->emulate)
		sd->buffer = fio_memalign(page_size, o->bs[DDIR_COPY], false);

	td->io_ops_data = sd;

	return 0;
}

static int fio_sctl_type_check(struct thread_data *td, struct fio_file *f)
{
	if (f->filetype != FIO_TYPE_BLOCK)
		return -EINVAL;

	return 0;
}

static int fio_sctl_open(struct thread_data *td, struct fio_file *f)
{

	int ret;

	ret = generic_open_file(td, f);
	if (ret)
		return ret;

	if (fio_sctl_type_check(td, f)) {
		ret = generic_close_file(td, f);
		return 1;
	}

	return 0;
}

static struct ioengine_ops ioengine = {
	.name			= "sctl",
	.version		= FIO_IOOPS_VERSION,
	.init			= fio_sctl_init,
	.prep			= fio_sctl_prep,
	.queue			= fio_sctl_queue,
	.cleanup		= fio_sctl_cleanup,
	.open_file		= fio_sctl_open,
	.close_file		= generic_close_file,
	.get_file_size		= generic_get_file_size,
	.flags			= FIO_SYNCIO,
	.options		= options,
	.option_struct_size	= sizeof(struct sctl_options),
};

static void fio_init fio_sctl_register(void)
{
	register_ioengine(&ioengine);
}

static void fio_exit fio_sctl_unregister(void)
{
	unregister_ioengine(&ioengine);
}
